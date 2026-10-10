#!/usr/bin/env python3
"""
Dual-channel MCP3008 sampler built on a producer/consumer thread pipeline.

Why threads here, and where they actually help
----------------------------------------------
    sampler thread(s)  ->  Queue  ->  recorder thread  ->  ring buffer  ->  main thread (plot)

    * Sampler threads own the timing-critical SPI reads, so the GUI never stalls
      the acquisition loop and vice versa.
    * The recorder thread does CSV matching/writing off the sampler's critical
      path, so a slow SD card can't drop samples.
    * The main thread only draws.

Three modes (--mode), because "two threads" is not automatically faster:
    sequential   1 thread reads CH0 then CH1 back-to-back. Lowest skew and the
                 highest throughput for a SINGLE chip - recommended default.
    threads      2 threads, one per channel, sharing one chip. The SPI bus is a
                 single shared resource, so the two reads are serialized by a
                 mutex anyway: same throughput as `sequential`, slightly worse
                 skew. Useful only if each channel needs its own independent
                 rate/logic.
    dual-device  2 threads, 2 physical MCP3008 chips (e.g. CE0 + CE1). No shared
                 bus, no mutex -> this is the only mode that samples CH0 and CH1
                 TRULY simultaneously.

Hardware (Raspberry Pi, SPI0), per chip:
    MCP3008 VDD -> 3.3V      VREF -> 3.3V (keep <= VDD, decouple with 0.1 uF)
    AGND/DGND -> GND
    CLK -> GPIO11 (SCLK)   DOUT -> GPIO9 (MISO)
    DIN -> GPIO10 (MOSI)   CS   -> GPIO8 (CE0) / GPIO7 (CE1 for 2nd chip)
    Enable SPI: sudo raspi-config -> Interface Options -> SPI  (ls /dev/spidev0.0)

Install:
    sudo apt install python3-spidev python3-matplotlib

Usage:
    python3 mcp3008_dual_threaded.py --simulate --duration 5
    python3 mcp3008_dual_threaded.py --mode dual-device --device1 1 --rate 2000
    python3 mcp3008_dual_threaded.py --duration 30 --csv data.csv --png plot.png
"""

import argparse
import csv
import math
import os
import queue
import random
import signal
import sys
import threading
import time
from collections import deque

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

CONVERSION_DELAY_S = 24e-6  # ~3 bytes over SPI at 1 MHz; used by the simulator


# --------------------------------------------------------------------------- #
# Thread-safe SPI bus
# --------------------------------------------------------------------------- #
class SpiBus:
    """One spidev handle + a mutex.

    The mutex is what makes multi-threaded access safe: an MCP3008 read is a
    3-byte transaction, and two threads interleaving bytes on the same bus would
    produce garbage. It also means two threads on ONE chip gain no throughput -
    the bus serializes them either way.
    """

    def __init__(self, bus=0, device=0, speed_hz=1_000_000):
        import spidev

        self.lock = threading.Lock()
        self.dev = spidev.SpiDev()
        self.dev.open(bus, device)
        self.dev.max_speed_hz = speed_hz
        self.dev.mode = 0

    def xfer(self, out):
        with self.lock:
            return self.dev.xfer2(list(out))

    def close(self):
        with self.lock:
            self.dev.close()


class SimBus:
    """Fake bus: sleeps for one conversion time so skew numbers are realistic."""

    def __init__(self, bus=0, device=0, speed_hz=1_000_000):
        self.lock = threading.Lock()
        self.t0 = time.perf_counter()
        self.device = device

    def xfer(self, out):
        with self.lock:
            t = time.perf_counter() - self.t0
            ch = out[1] >> 4          # config nibble: S/D bit + 3 channel bits
            single = bool(ch & 0b1000)
            channel = ch & 0b0111
            if single and channel == 0:
                v = 1.65 + 1.5 * math.sin(2 * math.pi * 0.7 * t)
            elif single and channel == 1:
                v = 1.65 + 1.2 * math.sin(2 * math.pi * 2.0 * t + 0.8)
            else:
                v = 1.65 + 0.9 * math.sin(2 * math.pi * 1.1 * t)
            v = min(max(v + random.gauss(0, 0.015), 0.0), 3.3)
            code = int(round(v / 3.3 * 1023))
            deadline = time.perf_counter() + CONVERSION_DELAY_S
            while time.perf_counter() < deadline:
                pass
            return [0x00, (code >> 8) & 0b11, code & 0xFF]

    def close(self):
        pass


class MCP3008:
    """A single MCP3008 hanging off a (possibly shared) bus."""

    def __init__(self, bus, vref=3.3):
        self.bus = bus
        self.vref = float(vref)

    def read_raw(self, channel, single_ended=True):
        if not 0 <= channel <= 7:
            raise ValueError("channel must be 0..7")
        cmd = (0b1000 | channel) if single_ended else (0b0000 | channel)
        resp = self.bus.xfer([0x01, cmd << 4, 0x00])
        return ((resp[1] & 0b00000011) << 8) | resp[2]

    def read_voltage(self, channel, single_ended=True):
        return self.read_raw(channel, single_ended) * self.vref / 1023.0


# --------------------------------------------------------------------------- #
# Shared sink: what the plotting thread reads
# --------------------------------------------------------------------------- #
class SampleSink:
    def __init__(self, capacity, history=1_000_000):
        self.lock = threading.Lock()
        # disp: bounded to the visible window, so drawing stays cheap.
        # hist: everything, kept for the FFT after you stop.
        self.t = {0: deque(maxlen=capacity), 1: deque(maxlen=capacity)}
        self.v = {0: deque(maxlen=capacity), 1: deque(maxlen=capacity)}
        self.ht = {0: deque(maxlen=history), 1: deque(maxlen=history)}
        self.hv = {0: deque(maxlen=history), 1: deque(maxlen=history)}

    def add(self, channel, t, v):
        with self.lock:
            self.t[channel].append(t)
            self.v[channel].append(v)
            self.ht[channel].append(t)
            self.hv[channel].append(v)

    def snapshot(self):
        with self.lock:
            return ({c: list(self.t[c]) for c in (0, 1)},
                    {c: list(self.v[c]) for c in (0, 1)})

    def history(self):
        with self.lock:
            return ({c: list(self.ht[c]) for c in (0, 1)},
                    {c: list(self.hv[c]) for c in (0, 1)})


# --------------------------------------------------------------------------- #
# Consumer thread: pairs CH0/CH1 by sample index, writes CSV, feeds the sink
# --------------------------------------------------------------------------- #
class Recorder(threading.Thread):
    """Does all blocking I/O off the sampler's critical path."""

    def __init__(self, q, sink, csv_path=None, forward_q=None, forward_every=25):
        super().__init__(daemon=True)
        self.q = q
        self.sink = sink
        self.csv_path = csv_path
        self.forward_q = forward_q
        self.forward_every = forward_every
        self.forward_buf = []
        self.pending = {}
        self.rows = 0
        self.skew_us = []
        self.t_min = None
        self.t_max = 0.0

    def run(self):
        fh = writer = None
        if self.csv_path:
            fh = open(self.csv_path, "w", newline="")
            writer = csv.writer(fh)
            writer.writerow(["index", "t_ch0_s", "ch0_v", "t_ch1_s", "ch1_v", "skew_us"])

        while True:
            item = self.q.get()
            if item is None:
                break
            index, channel, t, v = item
            slot = self.pending.setdefault(index, {})
            slot[channel] = (t, v)
            if 0 in slot and 1 in slot:
                t0, v0 = slot.pop(0)
                t1, v1 = slot.pop(1)
                self.pending.pop(index, None)
                self.sink.add(0, t0, v0)
                self.sink.add(1, t1, v1)
                self._account(t0, v0, t1, v1)
                if writer:
                    writer.writerow([index, f"{t0:.6f}", f"{v0:.4f}",
                                     f"{t1:.6f}", f"{v1:.4f}",
                                     f"{abs(t1 - t0) * 1e6:.1f}"])
        if fh:
            fh.close()

    def _account(self, t0, v0, t1, v1):
        """Track totals independently of the fixed-size plot ring buffer."""
        skew_us = abs(t1 - t0) * 1e6
        self.rows += 1
        self.skew_us.append(skew_us)
        lo, hi = min(t0, t1), max(t0, t1)
        self.t_min = lo if self.t_min is None else min(self.t_min, lo)
        self.t_max = max(self.t_max, hi)
        if self.forward_q is not None:
            self.forward_buf.append((t0, v0, t1, v1))
            if len(self.forward_buf) >= self.forward_every:
                self._flush_forward()

    def drain(self, q):
        """Flush half-finished pairs once the samplers have stopped."""
        while True:
            try:
                item = q.get_nowait()
            except queue.Empty:
                break
            if item is None:
                continue
            index, channel, t, v = item
            slot = self.pending.setdefault(index, {})
            slot[channel] = (t, v)
            if 0 in slot and 1 in slot:
                t0, v0 = slot.pop(0)
                t1, v1 = slot.pop(1)
                self.sink.add(0, t0, v0)
                self.sink.add(1, t1, v1)
                self._account(t0, v0, t1, v1)

    def _flush_forward(self):
        if self.forward_buf:
            self.forward_q.put(self.forward_buf)
            self.forward_buf = []


# --------------------------------------------------------------------------- #
# Producer threads
# --------------------------------------------------------------------------- #
class SamplerThread(threading.Thread):
    """One thread, one channel."""

    def __init__(self, channel, chip, rate, stop_event, out_q,
                 barrier=None, differential=False, duration=None):
        super().__init__(daemon=True)
        self.channel = channel
        self.chip = chip
        self.period = 1.0 / rate
        self.stop_event = stop_event
        self.out_q = out_q
        self.barrier = barrier
        self.differential = differential
        self.duration = duration
        self.t0 = None
        self.index = 0

    def _wait_for_next_round(self, deadline):
        if self.barrier is not None:
            try:
                self.barrier.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                return False
        remaining = deadline - time.perf_counter()
        if remaining > 0:
            # sleep() releases the GIL; only spin the sub-millisecond tail so we
            # don't starve the rendering thread.
            if remaining > 0.002:
                time.sleep(remaining - 0.001)
            while time.perf_counter() < deadline:
                pass
        return True

    def run(self):
        self.t0 = time.perf_counter()
        deadline = self.t0
        while not self.stop_event.is_set():
            deadline += self.period
            if not self._wait_for_next_round(deadline):
                break
            before = time.perf_counter()
            if self.differential:
                v = self.chip.read_voltage(0, single_ended=False)
            else:
                v = self.chip.read_voltage(self.channel, single_ended=True)
            # Midpoint of the transfer best estimates when the ADC actually
            # sampled the input.
            t = (before + time.perf_counter()) / 2 - self.t0
            self.out_q.put((self.index, self.channel, t, v))
            self.index += 1
            if self.duration is not None and t >= self.duration:
                self.stop_event.set()
                break
            if deadline < time.perf_counter() - self.period:
                deadline = time.perf_counter()


class SequentialSamplerThread(threading.Thread):
    """One thread reads both channels back-to-back: minimal skew, max throughput."""

    def __init__(self, chip, rate, stop_event, out_q, differential=False,
                 duration=None):
        super().__init__(daemon=True)
        self.chip = chip
        self.period = 1.0 / rate
        self.stop_event = stop_event
        self.out_q = out_q
        self.differential = differential
        self.duration = duration
        self.index = 0

    def run(self):
        t0 = time.perf_counter()
        deadline = t0
        while not self.stop_event.is_set():
            deadline += self.period
            remaining = deadline - time.perf_counter()
            if remaining > 0:
                if remaining > 0.002:
                    time.sleep(remaining - 0.001)
                while time.perf_counter() < deadline:
                    pass

            before = time.perf_counter()
            if self.differential:
                v = self.chip.read_voltage(0, single_ended=False)
                mid = (before + time.perf_counter()) / 2 - t0
                self.out_q.put((self.index, 0, mid, v))
                self.out_q.put((self.index, 1, mid, v))
            else:
                v0 = self.chip.read_voltage(0, single_ended=True)
                mid_a = (before + time.perf_counter()) / 2 - t0
                v1 = self.chip.read_voltage(1, single_ended=True)
                mid_b = (before + time.perf_counter()) / 2 - t0
                self.out_q.put((self.index, 0, mid_a, v0))
                self.out_q.put((self.index, 1, mid_b, v1))
            self.index += 1
            now = time.perf_counter() - t0
            if self.duration is not None and now >= self.duration:
                self.stop_event.set()
                break
            if deadline < time.perf_counter() - self.period:
                deadline = time.perf_counter()


# --------------------------------------------------------------------------- #
# Optional: run the whole acquisition pipeline in its own PROCESS
# --------------------------------------------------------------------------- #
def sampler_entry(cfg, forward_q, stop_ev, stats_q):
    """Child process: owns the SPI bus and its own GIL.

    This is the only way to get hard timing while matplotlib renders: a separate
    process has a separate GIL, so the renderer can hog its own interpreter for
    20 ms per frame without delaying a single ADC read.
    """
    # Ctrl+C reaches the whole foreground process group, child included. If the
    # child died on SIGINT it would never flush its final batch, so ignore it
    # here and let the parent's stop_event drive an orderly shutdown.
    try:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    except (ValueError, OSError):
        pass  # not in the main thread of the child (shouldn't happen)
    sys.setswitchinterval(cfg["switch_interval"])
    bus_cls = SimBus if cfg["simulate"] else SpiBus
    if cfg["mode"] == "dual-device":
        chip0 = MCP3008(bus_cls(cfg["bus"], cfg["device"], cfg["spi_speed"]), cfg["vref"])
        chip1 = MCP3008(bus_cls(cfg["bus"], cfg["device1"], cfg["spi_speed"]), cfg["vref"])
        chips = (chip0, chip1)
    else:
        chip0 = chip1 = MCP3008(bus_cls(cfg["bus"], cfg["device"], cfg["spi_speed"]),
                                cfg["vref"])
        chips = (chip0,)

    # Local sink is unused in the child; plotting data goes out via forward_q.
    sink = SampleSink(10, history=1)
    q = queue.Queue(maxsize=20000)
    recorder = Recorder(q, sink, cfg["csv"], forward_q=forward_q, forward_every=25)
    recorder.start()

    stop_event = _ThreadEvent(stop_ev)
    if cfg["mode"] == "sequential" or cfg["differential"]:
        threads = [SequentialSamplerThread(chip0, cfg["rate"], stop_event, q,
                                           cfg["differential"], cfg["duration"])]
    else:
        barrier = None if cfg["no_align"] else threading.Barrier(2)
        threads = [SamplerThread(i, chip0 if i == 0 else chip1, cfg["rate"],
                                 stop_event, q, barrier, cfg["differential"],
                                 cfg["duration"]) for i in (0, 1)]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    q.put(None)
    recorder.join(timeout=2.0)
    recorder.drain(q)
    recorder._flush_forward()

    span = (recorder.t_max - recorder.t_min) or 1e-9
    sk = recorder.skew_us or [0.0]
    stats_q.put({
        "rows": recorder.rows, "span": span,
        "skew_mean": sum(sk) / len(sk), "skew_max": max(sk),
    })
    forward_q.put(None)
    for c in chips:
        c.bus.close()


class _ThreadEvent:
    """Adapt a multiprocessing.Event to the threading.Event interface."""

    def __init__(self, mp_event):
        self.ev = mp_event

    def is_set(self):
        return self.ev.is_set()

    def set(self):
        self.ev.set()


# --------------------------------------------------------------------------- #
def stats(name, values):
    if not values:
        return f"{name}: no data"
    mean = sum(values) / len(values)
    return (f"{name}: mean {mean:.4f} V, min {min(values):.4f} V, "
            f"max {max(values):.4f} V")


# --------------------------------------------------------------------------- #
# Frequency-domain analysis, run once after acquisition stops
# --------------------------------------------------------------------------- #
class Spectrum:
    def __init__(self, t, v, resample_threshold=0.05):
        import numpy as np

        t = np.asarray(t, dtype=float)
        v = np.asarray(v, dtype=float)

        if t.size < 4:
            raise ValueError(f"need >= 4 samples for an FFT, got {t.size}")

        # Guard against the tiny timing jitter threaded sampling can introduce.
        if np.any(np.diff(t) <= 0):
            order = np.argsort(t, kind="stable")
            t, v = t[order], v[order]

        dt = float(np.median(np.diff(t)))
        dts = np.diff(t)
        self.jitter = float(np.std(dts) / dt) if dt > 0 else 0.0
        self.n_raw = t.size

        if self.jitter > resample_threshold:
            # The DFT assumes a uniform grid. With >5% jitter, resampling is
            # cheaper than the spectral smearing you'd otherwise get.
            t_u = t[0] + np.arange(t.size) * dt
            v = np.interp(t_u, t, v)
            t = t_u
            self.resampled = True
        else:
            self.resampled = False

        n = t.size
        self.dt = dt
        self.fs = 1.0 / dt
        self.duration = n * dt
        self.df = 1.0 / self.duration      # bin spacing = 1/record length
        self.nyquist = self.fs / 2.0

        self.dc = float(v.mean())
        x = v - self.dc                    # drop DC so it doesn't leak into bin 1

        w = np.hanning(n)                  # Hann: -31 dB sidelobes vs -13 dB
        amp = np.abs(np.fft.rfft(x * w)) * 2.0 / np.sum(w)   # coherent gain fix
        self.freq = np.fft.rfftfreq(n, dt)
        self.amp = amp

        # Peak search: skip the DC bin, use parabolic interpolation on the
        # three bins around the max for sub-bin frequency accuracy.
        if self.freq.size > 2:
            k = int(np.argmax(amp[1:])) + 1
            delta = 0.0
            if 0 < k < amp.size - 1:
                denom = amp[k - 1] - 2.0 * amp[k] + amp[k + 1]
                if denom != 0:
                    delta = 0.5 * (amp[k - 1] - amp[k + 1]) / denom
            self.peak_f = float((k + delta) * self.df)
            self.peak_a = float(amp[k])
            self.peak_bin = k
        else:
            self.peak_f, self.peak_a, self.peak_bin = float("nan"), 0.0, 0

        self.rms = float(np.sqrt(np.mean(x ** 2)))

    def top_peaks(self, count=3, floor_db=-40):
        """Simple local-maximum peak picking, returns (freq, amp) pairs."""
        import numpy as np

        a = self.amp
        out = []
        for i in range(1, a.size - 1):
            if a[i] > a[i - 1] and a[i] >= a[i + 1] and a[i] > 0:
                if 20 * np.log10(a[i] / max(self.peak_a, 1e-12)) >= floor_db:
                    out.append((self.freq[i], float(a[i])))
        out.sort(key=lambda p: -p[1])
        return out[:count]


def fft_figure(hist_t, hist_v, vref, log_scale=False, title=""):
    """2x2 overview: full time-domain record on top, spectra below."""
    import numpy as np

    spectra = {}
    for ch in (0, 1):
        try:
            spectra[ch] = Spectrum(hist_t[ch], hist_v[ch])
        except ValueError as exc:
            print(f"CH{ch}: FFT skipped ({exc})")
            spectra[ch] = None

    fig, axes = plt.subplots(2, 2, figsize=(12, 7))
    colors = {0: "tab:blue", 1: "tab:orange"}

    for ch in (0, 1):
        ax_t = axes[0, ch]
        t = hist_t[ch]
        v = hist_v[ch]
        stride = max(1, len(t) // 20000)
        ax_t.plot(t[::stride], v[::stride], lw=0.6, color=colors[ch])
        ax_t.set_title(f"CH{ch} time domain ({len(t)} samples)")
        ax_t.set_xlabel("Time (s)")
        ax_t.set_ylabel("Voltage (V)")
        ax_t.set_ylim(-0.05 * vref, 1.05 * vref)
        ax_t.grid(alpha=0.3)

        ax_f = axes[1, ch]
        sp = spectra[ch]
        if sp is None:
            ax_f.set_axis_off()
            continue
        ax_f.plot(sp.freq, sp.amp, lw=0.9, color=colors[ch])
        ax_f.axvline(sp.peak_f, ls="--", lw=0.8, color="crimson")
        ax_f.annotate(f"peak {sp.peak_f:.2f} Hz\n{sp.peak_a:.4f} V",
                      xy=(sp.peak_f, sp.peak_a),
                      xytext=(8, 8), textcoords="offset points", fontsize=8,
                      color="crimson")
        ax_f.set_xlim(0, sp.nyquist)
        ax_f.set_xlabel("Frequency (Hz)")
        ax_f.set_ylabel("Amplitude (V)")
        ax_f.set_yscale("log" if log_scale else "linear")
        if log_scale:
            ax_f.set_ylim(bottom=max(sp.amp.max() * 1e-4, 1e-6))
        else:
            ax_f.set_ylim(0, max(sp.peak_a * 1.25, 1e-3))
        ax_f.grid(alpha=0.3)
        ax_f.set_title(f"CH{ch} spectrum  (fs={sp.fs:.1f} Hz, "
                       f"Nyquist={sp.nyquist:.1f} Hz, df={sp.df:.3f} Hz)")

    if title:
        fig.suptitle(title)
    fig.tight_layout()
    return fig, spectra


def main():
    ap = argparse.ArgumentParser(description="Threaded dual-channel MCP3008 sampler + live plot")
    ap.add_argument("--mode", choices=("sequential", "threads", "dual-device"),
                    default="sequential",
                    help="sequential=1 thread/2 ch (default); threads=2 threads sharing "
                         "one chip; dual-device=2 threads on 2 chips (true simultaneity)")
    ap.add_argument("--bus", type=int, default=0)
    ap.add_argument("--device", type=int, default=0, help="CS of the first chip (CE0)")
    ap.add_argument("--device1", type=int, default=1, help="CS of the second chip (--mode dual-device)")
    ap.add_argument("--vref", type=float, default=3.3)
    ap.add_argument("--spi-speed", type=int, default=1_000_000)
    ap.add_argument("--rate", type=float, default=500.0, help="Samples/s per channel")
    ap.add_argument("--window", type=float, default=10.0, help="Visible window (s)")
    ap.add_argument("--duration", type=float, default=None, help="Stop after N seconds")
    ap.add_argument("--differential", action="store_true",
                    help="CH0=IN+, CH1=IN- (one value, not two signals)")
    ap.add_argument("--no-align", action="store_true",
                    help="Disable the per-round barrier between sampler threads")
    ap.add_argument("--csv", default=None)
    ap.add_argument("--png", default=None)
    ap.add_argument("--simulate", action="store_true")
    ap.add_argument("--headless", action="store_true")
    ap.add_argument("--switch-interval", type=float, default=5e-4,
                    help="sys.setswitchinterval(); lower = sampler threads wake "
                         "sooner when the render thread holds the GIL")
    ap.add_argument("--max-points", type=int, default=2000,
                    help="Decimate the plotted line to this many points")
    ap.add_argument("--isolate", action="store_true",
                    help="Run acquisition in a separate PROCESS (own GIL) so "
                         "rendering cannot delay or drop samples")
    ap.add_argument("--no-fft", action="store_true",
                    help="Skip the FFT after acquisition stops")
    ap.add_argument("--fft-log", action="store_true",
                    help="Log y-axis on the spectra (good for finding harmonics)")
    ap.add_argument("--max-history", type=int, default=1_000_000,
                    help="Samples per channel kept for the FFT (default 1e6, "
                         "~50 MB at most)")
    args = ap.parse_args()

    # CPython only hands the GIL to a waiting thread every `switchinterval`
    # seconds. matplotlib's renderer is pure Python and holds the GIL for whole
    # frames, so the default 5 ms can delay a sampler wake-up by milliseconds.
    sys.setswitchinterval(args.switch_interval)

    has_display = bool(os.environ.get("DISPLAY")) or sys.platform in ("win32", "darwin")
    if not args.headless and has_display:
        try:
            import tkinter  # noqa: F401

            matplotlib.use("TkAgg")
        except Exception:
            matplotlib.use("Agg")

    capacity = max(int(args.rate * args.window) + 10, 10)
    sink = SampleSink(capacity, args.max_history)

    cfg = dict(mode=args.mode, bus=args.bus, device=args.device, device1=args.device1,
               vref=args.vref, spi_speed=args.spi_speed, rate=args.rate,
               duration=args.duration, differential=args.differential,
               no_align=args.no_align, csv=args.csv, simulate=args.simulate,
               switch_interval=args.switch_interval)

    if args.isolate:
        import multiprocessing as mp

        ctx = mp.get_context("spawn")
        forward_q = ctx.Queue(maxsize=200)
        stats_q = ctx.Queue()
        stop_ev = ctx.Event()
        proc = ctx.Process(target=sampler_entry, args=(cfg, forward_q, stop_ev, stats_q),
                           daemon=True)
        proc.start()

        chip0 = chip1 = None
        threads = []
        barrier = None
        recorder = None
        stop_event = None

        def feed():
            """Drain the child's batches into the plotting sink."""
            while True:
                batch = forward_q.get()
                if batch is None:
                    break
                for t0, v0, t1, v1 in batch:
                    sink.add(0, t0, v0)
                    sink.add(1, t1, v1)
            incoming.set()

        incoming = threading.Event()
        feeder = threading.Thread(target=feed, daemon=True)
        feeder.start()
    else:
        bus_cls = SimBus if args.simulate else SpiBus
        try:
            if args.mode == "dual-device":
                chip0 = MCP3008(bus_cls(args.bus, args.device, args.spi_speed), args.vref)
                chip1 = MCP3008(bus_cls(args.bus, args.device1, args.spi_speed), args.vref)
            else:
                shared = MCP3008(bus_cls(args.bus, args.device, args.spi_speed), args.vref)
                chip0 = chip1 = shared
        except Exception as exc:
            sys.exit(f"Cannot open SPI device: {exc}\n"
                     f"Check that SPI is enabled (ls /dev/spidev{args.bus}.*). "
                     f"Use --simulate to exercise the thread pipeline without hardware.")

        q = queue.Queue(maxsize=capacity * 4)
        recorder = Recorder(q, sink, args.csv)
        recorder.start()

        stop_event = threading.Event()
        if args.mode == "sequential" or args.differential:
            threads = [SequentialSamplerThread(chip0, args.rate, stop_event, q,
                                               args.differential, args.duration)]
            barrier = None
        else:
            barrier = None if args.no_align else threading.Barrier(2)
            threads = [
                SamplerThread(0, chip0, args.rate, stop_event, q, barrier,
                              args.differential, args.duration),
                SamplerThread(1, chip1, args.rate, stop_event, q, barrier,
                              args.differential, args.duration),
            ]
        for th in threads:
            th.start()
        feeder = incoming = proc = stop_ev = None

    # ---------------- plotting (main thread) ----------------
    fig, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    if args.differential:
        axes[1].set_visible(False)
        (line0,) = axes[0].plot([], [], "-", lw=1.0, color="tab:blue")
        lines = [line0]
        axes[0].set_title("MCP3008 differential (CH0 = IN+, CH1 = IN-)  [threaded]")
        axes[0].set_ylabel("Voltage (V)")
        axes[0].set_xlabel("Time (s)")
        axes[0].legend([line0], ["CH0 - CH1"], loc="upper right")
    else:
        lines = []
        for ax, ch, color in zip(axes, ("CH0", "CH1"), ("tab:blue", "tab:orange")):
            (ln,) = ax.plot([], [], "-", lw=1.0, color=color)
            ax.set_ylabel("Voltage (V)")
            ax.set_title(f"MCP3008 {ch}")
            ax.grid(alpha=0.3)
            ax.set_ylim(-0.05 * args.vref, 1.05 * args.vref)
            lines.append(ln)
        axes[1].set_xlabel("Time (s)")

    def update(_frame):
        tt, vv = sink.snapshot()
        if not tt[0]:
            return lines
        # Decimate: drawing 50k points costs tens of ms of GIL time per frame,
        # which directly delays the sampler threads.
        stride = max(1, len(tt[0]) // args.max_points)
        last = max(tt[0][-1], tt[1][-1])
        for ax, ln, ch in zip(axes, lines, (0, 1)):
            ln.set_data(tt[ch][::stride], vv[ch][::stride])
            ax.set_xlim(max(0, last - args.window), max(args.window, last))
        return lines

    interactive = "agg" not in matplotlib.get_backend().lower()
    # Only start the animation when there is a screen to draw on; in headless
    # mode the figures are written to PNG at the end instead.
    anim = (FuncAnimation(fig, update, interval=50, blit=False, cache_frame_data=False)
            if interactive else None)
    fig.tight_layout()

    running = (lambda: proc.is_alive()) if args.isolate else \
              (lambda: any(t.is_alive() for t in threads))

    stopped_by = "duration"
    try:
        if interactive:
            # Always drive the event loop ourselves instead of a blocking show():
            # that keeps Python in the main thread, so SIGINT is delivered
            # promptly (a blocking Tk/Qt mainloop often swallows Ctrl+C).
            plt.show(block=False)
            while running():
                plt.pause(0.05)
                if not plt.get_fignums():   # window closed == stop request
                    stopped_by = "window closed"
                    break
        else:
            while running():
                time.sleep(0.05)
    except KeyboardInterrupt:
        stopped_by = "Ctrl+C"
    finally:
        if args.isolate:
            stop_ev.set()
            proc.join(timeout=3.0)
            if proc.is_alive():
                proc.terminate()
                proc.join(timeout=2.0)
            incoming.wait(timeout=2.0)
        else:
            stop_event.set()
            if barrier is not None:
                barrier.abort()
            for th in threads:
                th.join(timeout=2.0)
            q.put(None)
            recorder.join(timeout=2.0)
            recorder.drain(q)
            if args.mode == "dual-device":
                chip0.bus.close()
                chip1.bus.close()
            else:
                chip0.bus.close()

    tt, vv = sink.snapshot()
    hist_t, hist_v = sink.history()
    if min(len(hist_t[0]), len(hist_t[1])) < 1:
        print("No samples collected.")
        return

    if args.isolate:
        try:
            st = stats_q.get(timeout=2.0)
        except Exception:
            st = None
        print(f"\nmode={args.mode} (isolated process)  "
              f"barrier={'off' if args.no_align else 'on'}")
        if st and st["rows"]:
            print(f"Recorded {st['rows']} pairs over {st['span']:.2f} s "
                  f"-> {st['rows'] / st['span']:.1f} S/s per channel "
                  f"(target {args.rate:g})")
            print(f"CH0/CH1 skew: mean {st['skew_mean']:.1f} us, "
                  f"max {st['skew_max']:.1f} us")
        else:
            print(f"Child did not report statistics; using the "
                  f"{min(len(hist_t[0]), len(hist_t[1]))} samples the parent "
                  f"received before shutdown.")
            n = min(len(hist_t[0]), len(hist_t[1]))
            span = (max(hist_t[0][-1], hist_t[1][-1])
                    - min(hist_t[0][0], hist_t[1][0])) or 1e-9
            print(f"Recorded ~{n} pairs over {span:.2f} s "
                  f"-> ~{n / span:.1f} S/s per channel")
    else:
        span = (recorder.t_max - recorder.t_min) or 1e-9
        print(f"\nmode={args.mode}  sampler threads={len(threads)}  "
              f"barrier={'off' if args.no_align else 'on'}")
        print(f"Recorded {recorder.rows} pairs over {span:.2f} s "
              f"-> {recorder.rows / span:.1f} S/s per channel (target {args.rate:g})")
        sk = recorder.skew_us
        print(f"CH0/CH1 skew: mean {sum(sk)/len(sk):.1f} us, max {max(sk):.1f} us")
    print(stats("CH0", vv[0]))
    print(stats("CH1", vv[1]))
    if args.csv:
        print(f"CSV saved -> {args.csv}")
    if args.png:
        fig.savefig(args.png, dpi=150)
        print(f"Time-domain figure saved -> {args.png}")

    # ---------------- frequency-domain analysis ----------------
    if args.no_fft:
        return

    hist_t, hist_v = sink.history()
    if len(hist_t[0]) < 4:
        print("\nNot enough samples for an FFT.")
        return

    print(f"\nStopped by: {stopped_by}")
    print("=" * 62)
    print("FREQUENCY DOMAIN (FFT of the whole record)")
    print("=" * 62)

    fft_fig, spectra = fft_figure(hist_t, hist_v, args.vref,
                                  log_scale=args.fft_log,
                                  title=f"MCP3008 FFT - mode={args.mode}")
    for ch in (0, 1):
        sp = spectra.get(ch)
        if sp is None:
            continue
        print(f"\nCH{ch}: {sp.n_raw} samples, {sp.duration:.2f} s record, "
              f"fs={sp.fs:.1f} Hz, Nyquist={sp.nyquist:.1f} Hz")
        print(f"      bin spacing df={sp.df:.4f} Hz  (df = 1/record length)")
        print(f"      DC offset {sp.dc:.4f} V, AC RMS {sp.rms:.4f} V")
        print(f"      resampled to uniform grid: {'yes' if sp.resampled else 'no'} "
              f"(timing jitter {sp.jitter * 100:.2f}% of dt)")
        print(f"      PEAK {sp.peak_f:.3f} Hz at {sp.peak_a:.4f} V amplitude")
        peaks = sp.top_peaks(3)
        if len(peaks) > 1:
            txt = ", ".join(f"{f:.2f} Hz ({a:.4f} V)" for f, a in peaks)
            print(f"      other peaks: {txt}")
        # Honest caveats rather than a bare number.
        if sp.peak_f < 2 * sp.df:
            print("      ! peak is within 2 bins of DC: record too short to "
                  "resolve it, capture longer")
        if sp.peak_f > 0.8 * sp.nyquist:
            print("      ! peak is above 0.8 x Nyquist: add an anti-aliasing "
                  "RC filter and sample faster")
        if sp.resampled:
            print("      ! sampling jitter was high; consider --isolate or "
                  "--mode sequential for a cleaner spectrum")

    if args.png:
        stem, dot = os.path.splitext(args.png)
        fft_path = f"{stem}_fft{dot or '.png'}"
        fft_fig.savefig(fft_path, dpi=150)
        print(f"\nFFT figure saved -> {fft_path}")

    backend = matplotlib.get_backend().lower()
    if "agg" not in backend:
        print("\nShowing FFT window - close it to exit.")
        plt.figure(fft_fig.number)
        plt.show()
    else:
        print("\nNo display available: FFT figure was saved instead of shown.")


if __name__ == "__main__":
    main()
