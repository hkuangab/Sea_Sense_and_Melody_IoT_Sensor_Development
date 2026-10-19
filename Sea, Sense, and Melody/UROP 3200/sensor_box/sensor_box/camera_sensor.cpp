/**
 * @file camera_sensor.cpp
 * @brief Implementation of the libcamera camera module with SDL2 display.
 *
 * See camera_sensor.h for the full interface documentation.
 *
 * This file implements the camera worker thread that captures frames at
 * 5 fps, converts YUV to HSV, builds a 3D histogram, sorts the bins by
 * count, and extracts the top‑3 colour clusters. The live feed is
 * displayed in an SDL2 window with overlay text showing colour swatches
 * and the latest emotion classification.
 *
 * The implementation uses libcamera 0.7.x (PiSP) with multi‑buffer
 * safety: all buffers are allocated upfront and recycled via a
 * completion callback.
 *
 * Author: KUANG, Haozhe
 * Affiliation: The Hong Kong University of Science and Technology
 * Email: hkuangab@connect.ust.hk
 * Date:   2026/10/19
 */

/*
 * camera_sensor.cpp – libcamera 0.7.x (PiSP) multi-buffer safe version
 * Author: KUANG, Haozhe (HKUST)
 * Date:   2026/10/19
 * Modified: emotion label stored as string, displayed as text on camera window
 */

#include "camera_sensor.h"
#include "sensor_box.h"

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <condition_variable>
#include <cstdio>
#include <cstring>
#include <cerrno>
#include <fcntl.h>
#include <libcamera/camera.h>
#include <libcamera/camera_manager.h>
#include <libcamera/controls.h>
#include <libcamera/formats.h>
#include <libcamera/framebuffer_allocator.h>
#include <libcamera/request.h>
#include <libcamera/stream.h>
#include <mqueue.h>
#include <mutex>
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <thread>
#include <unistd.h>
#include <vector>

using namespace libcamera;

/* ---------- Constants ---------- */
#define IMG_WIDTH       320
#define IMG_HEIGHT      240
#define DISPLAY_SCALE   1
#define CAMERA_FPS      5
#define SAMPLE_STEP     8
#define SDL_UPDATE_EVERY_N_FRAMES  2

#define H_BINS  8
#define S_BINS  16
#define V_BINS  16
#define TOP_N   3

#define DEBUG_PRINT_INTERVAL 30

/* ---------- Globals ---------- */

/**
 * @brief Worker thread handle for the camera capture loop.
 */
static std::thread g_cam_thread;

/**
 * @brief Atomic flag controlling the camera worker loop.
 * Set to true by camera_init(), set to false by camera_close().
 */
static std::atomic<bool> g_cam_running{false};

/**
 * @brief Atomic count of dominant colour clusters found (0..3).
 */
static std::atomic<int> g_top_count{0};

/**
 * @brief Atomic hue bin indices for the top-3 clusters.
 */
static std::atomic<int> g_top_h[TOP_N];

/**
 * @brief Atomic saturation bin indices for the top-3 clusters.
 */
static std::atomic<int> g_top_s[TOP_N];

/**
 * @brief Atomic value (brightness) bin indices for the top-3 clusters.
 */
static std::atomic<int> g_top_v[TOP_N];

/**
 * @brief Atomic pixel ratios for the top-3 clusters.
 */
static std::atomic<float> g_top_ratio[TOP_N];

/**
 * @brief Mutex protecting the emotion label string and confidence.
 */
static std::mutex g_emotion_mutex;

/**
 * @brief Internal buffer for the emotion label string.
 */
static char g_emotion_label_str[64] = "";

/**
 * @brief Internal storage for the emotion confidence value.
 */
static float g_emotion_conf_val = 0.0f;

/**
 * @brief SDL window handle. NULL until initSDL() succeeds.
 */
static SDL_Window   *g_window   = nullptr;

/**
 * @brief SDL renderer handle.
 */
static SDL_Renderer *g_renderer = nullptr;

/**
 * @brief SDL texture for the YUV camera image.
 */
static SDL_Texture  *g_texture  = nullptr;

/**
 * @brief TTF font handle for overlay text.
 */
static TTF_Font     *g_font     = nullptr;

/**
 * @brief Flag indicating that SDL initialisation succeeded.
 */
static bool          g_sdl_ok   = false;

/**
 * @brief POSIX message queue descriptor for sending colour data.
 * Opened in camera_init(), closed in camera_close().
 */
static mqd_t g_cam_mq_send = (mqd_t)-1;

/**
 * @brief Mutex protecting the completed request variable.
 */
static std::mutex              g_req_mtx;

/**
 * @brief Condition variable signalled when a request completes.
 */
static std::condition_variable g_req_cv;

/**
 * @brief Pointer to the most recently completed libcamera request.
 */
static Request                *g_completed_req = nullptr;

/* Forward declarations of internal helper functions. */
static bool initSDL();
static void destroySDL();
static void updateDisplay(const uint8_t *yuv, int stride, size_t buf_len);
static void yuv_to_rgb(uint8_t Y, uint8_t U, uint8_t V, int &r, int &g, int &b);
static void yuv_to_hsv_bin(uint8_t Y, uint8_t U, uint8_t V, int *hb, int *sb, int *vb);

/* ---------- Callback ---------- */

/**
 * @brief Callback invoked by libcamera when a request completes.
 *
 * Stores the completed request pointer and notifies the worker thread
 * via condition variable.
 *
 * @param[in] req  Pointer to the completed Request object.
 * @return void.
 */
static void onRequestComplete(Request *req)
{
    std::lock_guard<std::mutex> lock(g_req_mtx);
    g_completed_req = req;
    g_req_cv.notify_one();
}

/* ---------- YUV helpers ---------- */

/**
 * @brief Convert a single YUV pixel to RGB.
 *
 * Uses the standard BT.601 conversion formulae.
 *
 * @param[in]  Y  Luma component (0..255).
 * @param[in]  U  Blue‑difference chroma (0..255).
 * @param[in]  V  Red‑difference chroma (0..255).
 * @param[out] r  Red component (0..255).
 * @param[out] g  Green component (0..255).
 * @param[out] b  Blue component (0..255).
 * @return void.
 */
static void yuv_to_rgb(uint8_t Y, uint8_t U, uint8_t V, int &r, int &g, int &b)
{
    r = Y + 1.402f * (V - 128);
    g = Y - 0.344f * (U - 128) - 0.714f * (V - 128);
    b = Y + 1.772f * (U - 128);
    if (r < 0) r = 0;
    if (r > 255) r = 255;
    if (g < 0) g = 0;
    if (g > 255) g = 255;
    if (b < 0) b = 0;
    if (b > 255) b = 255;
}

/**
 * @brief Convert a YUV pixel to quantised HSV bin indices.
 *
 * First converts to RGB, then to HSV, then maps each component into
 * a bin index using the constant bin counts H_BINS, S_BINS, V_BINS.
 *
 * @param[in]  Y   Luma component.
 * @param[in]  U   Blue‑difference chroma.
 * @param[in]  V   Red‑difference chroma.
 * @param[out] hb  Hue bin index (0..H_BINS-1).
 * @param[out] sb  Saturation bin index (0..S_BINS-1).
 * @param[out] vb  Value bin index (0..V_BINS-1).
 * @return void.
 */
static void yuv_to_hsv_bin(uint8_t Y, uint8_t U, uint8_t V, int *hb, int *sb, int *vb)
{
    int r, g, b;
    yuv_to_rgb(Y, U, V, r, g, b);
    float rf = r/255.0f, gf = g/255.0f, bf = b/255.0f;
    float mx = std::max({rf, gf, bf});
    float mn = std::min({rf, gf, bf});
    float delta = mx - mn;
    float h = 0.0f;
    if (delta > 0.001f) {
        if (mx == rf)      h = 60.0f * fmod((gf-bf)/delta, 6.0f);
        else if (mx == gf) h = 60.0f * ((bf-rf)/delta + 2.0f);
        else               h = 60.0f * ((rf-gf)/delta + 4.0f);
    }
    if (h < 0) h += 360.0f;
    float s = (mx > 0.001f) ? (delta/mx) : 0.0f;
    float v = mx;

    *hb = (int)(h / (360.0f/H_BINS));
    *sb = (int)(s / (1.0f/S_BINS));
    *vb = (int)(v / (1.0f/V_BINS));
    if (*hb >= H_BINS) *hb = H_BINS-1;
    if (*sb >= S_BINS) *sb = S_BINS-1;
    if (*vb >= V_BINS) *vb = V_BINS-1;
}

/* ---------- Worker ---------- */

/**
 * @brief Main body of the camera capture thread.
 *
 * Performs the following steps:
 *   1. Initialise SDL2 and TTF.
 *   2. Open the libcamera CameraManager and acquire the first camera.
 *   3. Generate and validate a VideoRecording stream configuration.
 *   4. Allocate frame buffers and map them into userspace.
 *   5. Create and queue requests for each buffer.
 *   6. Loop: wait for a completed request, extract YUV data, compute
 *      the 3D HSV histogram, sort bins, store top‑3 clusters, send
 *      data over the message queue, update the SDL display, and
 *      requeue the request.
 *   7. On exit, clean up all resources.
 *
 * @param None (the function signature matches std::thread requirements).
 * @return void.
 */
static void camera_worker()
{
    printf("[camera_worker] starting (5 fps, step %d)\n", SAMPLE_STEP);

    if (!initSDL()) { fprintf(stderr, "[camera_worker] SDL init failed\n"); return; }
    g_sdl_ok = true;

    auto cm = std::make_unique<CameraManager>();
    if (cm->start()) { fprintf(stderr, "CameraManager start failed\n"); destroySDL(); return; }

    auto cameras = cm->cameras();
    if (cameras.empty()) { fprintf(stderr, "no cameras\n"); cm->stop(); destroySDL(); return; }

    auto camera = cameras[0];
    if (camera->acquire()) { fprintf(stderr, "acquire failed\n"); cm->stop(); destroySDL(); return; }

    auto cfg = camera->generateConfiguration({StreamRole::VideoRecording});
    if (!cfg) { fprintf(stderr, "genConfig failed\n"); camera->release(); cm->stop(); destroySDL(); return; }

    StreamConfiguration &sc = cfg->at(0);
    sc.pixelFormat = formats::YUYV;
    sc.size = {IMG_WIDTH, IMG_HEIGHT};

    if (cfg->validate() == CameraConfiguration::Invalid) {
        fprintf(stderr, "config invalid\n"); camera->release(); cm->stop(); destroySDL(); return;
    }
    if (camera->configure(cfg.get())) {
        fprintf(stderr, "configure failed\n"); camera->release(); cm->stop(); destroySDL(); return;
    }

    Stream *stream = sc.stream();
    unsigned stride = sc.stride;

    auto allocator = std::make_unique<FrameBufferAllocator>(camera);
    int alloc_ret = allocator->allocate(stream);
    if (alloc_ret < 0) {
        fprintf(stderr, "allocate failed raw_ret=%d errno=%d (%s)\n",
                alloc_ret, -alloc_ret, strerror(-alloc_ret));
        camera->release(); cm->stop(); destroySDL(); return;
    }

    const auto &buffers = allocator->buffers(stream);
    if (buffers.empty()) {
        fprintf(stderr, "no buffers\n"); allocator->free(stream);
        camera->release(); cm->stop(); destroySDL(); return;
    }
    printf("[camera_worker] allocated %zu buffers, stride=%u\n", buffers.size(), stride);

    /**
     * @brief Structure mapping a FrameBuffer to its userspace pointer and length.
     */
    struct BufMap {
        FrameBuffer *fb;
        uint8_t *ptr;
        size_t len;
    };
    std::vector<BufMap> mapped;
    for (auto &b : buffers) {
        const auto &planes = b->planes();
        if (planes.empty()) {
            fprintf(stderr, "buffer has no planes\n");
            goto fail_exit;
        }
        const auto &plane = planes[0];
        void *p = mmap(nullptr, plane.length, PROT_READ, MAP_SHARED, plane.fd.get(), 0);
        if (p == MAP_FAILED) { perror("mmap"); goto fail_exit; }
        mapped.push_back({b.get(), static_cast<uint8_t*>(p), plane.length});
    }

    {
        std::vector<std::unique_ptr<Request>> reqs;
        for (auto &m : mapped) {
            auto req = camera->createRequest();
            if (!req || req->addBuffer(stream, m.fb)) {
                fprintf(stderr, "createRequest/addBuffer failed\n");
                goto fail_exit;
            }
            reqs.push_back(std::move(req));
        }

        camera->requestCompleted.connect(onRequestComplete);

        if (camera->start()) {
            fprintf(stderr, "start failed\n");
            camera->requestCompleted.disconnect(onRequestComplete);
            goto fail_exit;
        }

        for (auto &req : reqs) {
            if (camera->queueRequest(req.get())) {
                fprintf(stderr, "initial queueRequest failed\n");
                camera->stop();
                camera->requestCompleted.disconnect(onRequestComplete);
                goto fail_exit;
            }
        }

        int frame_num = 0;
        while (g_cam_running.load()) {
            std::unique_lock<std::mutex> lock(g_req_mtx);
            bool timed_out = !g_req_cv.wait_for(lock, std::chrono::milliseconds(500),
                                []{ return g_completed_req != nullptr; });
            if (timed_out) { fprintf(stderr, "timeout\n"); continue; }

            Request *completed = g_completed_req;
            g_completed_req = nullptr;
            lock.unlock();

            if (completed->status() != Request::RequestComplete) {
                completed->reuse(Request::ReuseBuffers);
                camera->queueRequest(completed);
                continue;
            }

            FrameBuffer *fb = completed->buffers().begin()->second;
            uint8_t *yuv = nullptr;
            size_t buf_len = 0;
            for (auto &m : mapped)
                if (m.fb == fb) { yuv = m.ptr; buf_len = m.len; break; }

            if (yuv) {
                /**
                 * 3D histogram: H_BINS × S_BINS × V_BINS.
                 */
                int hist[H_BINS][S_BINS][V_BINS] = {{{0}}};
                int half = SAMPLE_STEP / 2;
                long sr=0, sg=0, sb=0;
                int cnt=0;

                /* Subsample the frame at stride SAMPLE_STEP. */
                for (int y = half; y < IMG_HEIGHT; y += SAMPLE_STEP) {
                    for (int x = half; x < IMG_WIDTH; x += SAMPLE_STEP) {
                        int sx = IMG_WIDTH - 1 - x;
                        int sy = IMG_HEIGHT - 1 - y;
                        int xx = sx & ~1;
                        if (xx+1 >= IMG_WIDTH) xx = IMG_WIDTH-2;
                        size_t offset = sy * stride + xx * 2;
                        if (offset + 4 > buf_len) continue;
                        const uint8_t *row = yuv + offset;
                        uint8_t Y0 = row[0];
                        uint8_t U  = row[1];
                        uint8_t V  = row[3];

                        int hb,sb_,vb;
                        yuv_to_hsv_bin(Y0,U,V,&hb,&sb_,&vb);
                        if (hb>=0) hist[hb][sb_][vb]++;

                        int r,g,b; yuv_to_rgb(Y0,U,V,r,g,b);
                        sr+=r; sg+=g; sb+=b; cnt++;
                    }
                }

                /* Collect non‑empty bins and sort descending by count. */
                struct Bin{int h,s,v,c;};
                std::vector<Bin> bins;
                for(int h=0;h<H_BINS;++h)
                for(int s=0;s<S_BINS;++s)
                for(int v=0;v<V_BINS;++v)
                    if(hist[h][s][v]>0) bins.push_back({h,s,v,hist[h][s][v]});
                std::sort(bins.begin(),bins.end(),[](auto&a,auto&b){return a.c>b.c;});

                int n = std::min((int)bins.size(), TOP_N);
                g_top_count.store(n);
                for(int i=0;i<n;++i){
                    g_top_h[i]=bins[i].h;
                    g_top_s[i]=bins[i].s;
                    g_top_v[i]=bins[i].v;
                    g_top_ratio[i] = (float)bins[i].c / (float)cnt;
                }
                for(int i=n;i<TOP_N;++i){
                    g_top_ratio[i] = 0.0f;
                }

                /* Send colour data over the message queue. */
                if (g_cam_mq_send != (mqd_t)-1) {
                    CamMessage msg;
                    msg.timestamp_ms = (uint64_t)time(NULL)*1000;
                    msg.top_count = n;
                    for(int i=0;i<TOP_N;++i){
                        msg.top_h[i]=(i<n)?bins[i].h:0;
                        msg.top_s[i]=(i<n)?bins[i].s:0;
                        msg.top_v[i]=(i<n)?bins[i].v:0;
                    }
                    mq_send(g_cam_mq_send,(const char*)&msg,sizeof(msg),0);
                }

                /* Update the SDL window every SDL_UPDATE_EVERY_N_FRAMES frames. */
                if (frame_num % SDL_UPDATE_EVERY_N_FRAMES == 0)
                    updateDisplay(yuv, stride, buf_len);

                if (frame_num % DEBUG_PRINT_INTERVAL == 0) {
                    fprintf(stderr, "[dbg f%d] avgRGB=(%ld,%ld,%ld) samples=%d\n",
                        frame_num, cnt?sr/cnt:0L, cnt?sg/cnt:0L, cnt?sb/cnt:0L, cnt);
                    fprintf(stderr, "  top: ");
                    for(int i=0;i<n;++i) fprintf(stderr,"#%d=(%d,%d,%d,%.3f) ",i+1,bins[i].h,bins[i].s,bins[i].v,g_top_ratio[i].load());
                    fprintf(stderr, "\n");
                }
            }

            frame_num++;

            completed->reuse(Request::ReuseBuffers);
            camera->queueRequest(completed);

            /* Throttle to the configured frame rate. */
            std::this_thread::sleep_for(std::chrono::milliseconds(1000/CAMERA_FPS));
        }

        camera->requestCompleted.disconnect(onRequestComplete);
        camera->stop();
    }

fail_exit:
    for (auto &m : mapped)
        munmap(m.ptr, m.len);
    allocator->free(stream);
    camera->release();
    cm->stop();
    destroySDL();
    printf("[camera_worker] stopped\n");
}

/* ---------- Public API ---------- */

/**
 * @brief Open the libcamera camera and start the capture thread.
 *
 * Creates the POSIX message queue (non‑fatal if it fails), sets the
 * running flag, and spawns the camera worker thread.
 *
 * @return 0 on success, -1 on failure (currently always returns 0).
 */
int camera_init()
{
    struct mq_attr attr;
    attr.mq_flags=0; attr.mq_maxmsg=CAM_MQ_MAXMSG;
    attr.mq_msgsize=sizeof(CamMessage); attr.mq_curmsgs=0;
    g_cam_mq_send = mq_open(CAM_MQ_NAME, O_CREAT|O_WRONLY|O_NONBLOCK, 0644, &attr);
    if (g_cam_mq_send == (mqd_t)-1) perror("mq_open (non-fatal)");

    g_cam_running = true;
    g_cam_thread = std::thread(camera_worker);
    return 0;
}

/**
 * @brief Capture one frame and compute HSV statistics.
 *
 * Intentionally empty; the actual capture runs continuously in the
 * worker thread. Retained for interface compatibility.
 *
 * @param None.
 * @return void.
 */
void camera_sample(){}

/**
 * @brief Stop the camera worker thread and release all resources.
 *
 * Signals the worker to stop, joins the thread, closes and unlinks the
 * message queue, and sets the queue descriptor to -1.
 *
 * @param None.
 * @return void.
 */
void camera_close()
{
    g_cam_running = false;
    if (g_cam_thread.joinable()) g_cam_thread.join();
    if (g_cam_mq_send != (mqd_t)-1) {
        mq_close(g_cam_mq_send); mq_unlink(CAM_MQ_NAME); g_cam_mq_send=(mqd_t)-1;
    }
}

/**
 * @brief Get the number of dominant colour clusters found.
 * @return int Number of clusters (0..3).
 */
int camera_get_top_count(){return g_top_count.load();}

/**
 * @brief Get the hue bin index of the i-th dominant colour.
 * @param i  Cluster index (0, 1, 2).
 * @return int Hue bin index, or 0 if index is out of range.
 */
int camera_get_top_h(int i){return (i>=0&&i<TOP_N)?g_top_h[i].load():0;}

/**
 * @brief Get the saturation bin index of the i-th dominant colour.
 * @param i  Cluster index (0, 1, 2).
 * @return int Saturation bin index, or 0 if index is out of range.
 */
int camera_get_top_s(int i){return (i>=0&&i<TOP_N)?g_top_s[i].load():0;}

/**
 * @brief Get the value bin index of the i-th dominant colour.
 * @param i  Cluster index (0, 1, 2).
 * @return int Value bin index, or 0 if index is out of range.
 */
int camera_get_top_v(int i){return (i>=0&&i<TOP_N)?g_top_v[i].load():0;}

/**
 * @brief Get the pixel ratio of the i-th dominant colour cluster.
 * @param i  Cluster index (0, 1, 2).
 * @return float Ratio in [0.0, 1.0], or 0.0 if index is out of range.
 */
float camera_get_top_ratio(int i){return (i>=0&&i<TOP_N)?g_top_ratio[i].load():0.0f;}

/* Emotion string storage (thread-safe) */

/**
 * @brief Store the latest emotion classification result.
 *
 * Copies the label string (up to 63 characters) and confidence value
 * under the protection of g_emotion_mutex.
 *
 * @param[in] label       Null‑terminated emotion string. May be NULL.
 * @param[in] confidence  Confidence in [0.0, 1.0].
 * @return void.
 */
void camera_set_emotion(const char *label, float confidence)
{
    std::lock_guard<std::mutex> lock(g_emotion_mutex);
    if (label) {
        strncpy(g_emotion_label_str, label, sizeof(g_emotion_label_str)-1);
        g_emotion_label_str[sizeof(g_emotion_label_str)-1] = '\0';
    } else {
        g_emotion_label_str[0] = '\0';
    }
    g_emotion_conf_val = confidence;
}

/**
 * @brief Get the stored emotion label string.
 *
 * Returns a pointer to the internal buffer. The caller should copy the
 * string if needed beyond the next call. Thread‑safe.
 *
 * @return const char* Pointer to the label string (may be empty).
 */
const char *camera_get_emotion_label(void)
{
    // Return pointer to internal buffer; caller should copy if needed
    // Thread-safety: only called from main thread during build_snapshot
    // We still lock briefly to ensure consistency
    std::lock_guard<std::mutex> lock(g_emotion_mutex);
    return g_emotion_label_str;
}

/**
 * @brief Get the stored emotion confidence.
 *
 * @return float Confidence in [0.0, 1.0].
 */
float camera_get_emotion_conf(void)
{
    std::lock_guard<std::mutex> lock(g_emotion_mutex);
    return g_emotion_conf_val;
}

/**
 * @brief Update the SDL window title with the current emotion classification.
 *
 * Reads the emotion label and confidence under the mutex, formats a
 * title string, and calls SDL_SetWindowTitle(). No effect if the window
 * does not exist.
 *
 * @param None.
 * @return void.
 */
void camera_set_window_title()
{
    if(!g_window) return;
    char t[128];
    // Use local copies to avoid holding lock while calling SDL
    std::lock_guard<std::mutex> lock(g_emotion_mutex);
    snprintf(t,sizeof(t),"SensorBox - Emotion: %s (%.1f%%)",
             g_emotion_label_str[0] ? g_emotion_label_str : "None",
             g_emotion_conf_val*100);
    SDL_SetWindowTitle(g_window,t);
}

/* ---------- SDL ---------- */

/**
 * @brief Initialise SDL2, TTF, and create the display window.
 *
 * Initialises video subsystem, creates a window, renderer, and texture
 * in YUYV format. Loads a TrueType font for overlay text (non‑fatal if
 * the font file is missing).
 *
 * @return true on success, false on failure.
 */
static bool initSDL()
{
    if (SDL_Init(SDL_INIT_VIDEO)<0){fprintf(stderr,"SDL_Init %s\n",SDL_GetError());return false;}
    if (TTF_Init()<0){fprintf(stderr,"TTF_Init %s\n",TTF_GetError());SDL_Quit();return false;}
    g_window = SDL_CreateWindow("SensorBox",SDL_WINDOWPOS_UNDEFINED,SDL_WINDOWPOS_UNDEFINED,
                                IMG_WIDTH*DISPLAY_SCALE,IMG_HEIGHT*DISPLAY_SCALE,SDL_WINDOW_SHOWN);
    if(!g_window){TTF_Quit();SDL_Quit();return false;}
    g_renderer = SDL_CreateRenderer(g_window,-1,SDL_RENDERER_ACCELERATED);
    if(!g_renderer){SDL_DestroyWindow(g_window);TTF_Quit();SDL_Quit();return false;}
    g_texture = SDL_CreateTexture(g_renderer,SDL_PIXELFORMAT_YUY2,
                                  SDL_TEXTUREACCESS_STREAMING,IMG_WIDTH,IMG_HEIGHT);
    if(!g_texture){SDL_DestroyRenderer(g_renderer);SDL_DestroyWindow(g_window);TTF_Quit();SDL_Quit();return false;}
    g_font = TTF_OpenFont("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",14);
    if(!g_font) fprintf(stderr,"font missing (non-fatal)\n");
    return true;
}

/**
 * @brief Destroy all SDL resources.
 *
 * Closes font, texture, renderer, and window. Quits TTF and SDL subsystems.
 * Safe to call even if some handles are NULL.
 *
 * @param None.
 * @return void.
 */
static void destroySDL()
{
    if(g_font) TTF_CloseFont(g_font);
    if(g_texture) SDL_DestroyTexture(g_texture);
    if(g_renderer) SDL_DestroyRenderer(g_renderer);
    if(g_window) SDL_DestroyWindow(g_window);
    TTF_Quit(); SDL_Quit();
}

/**
 * @brief Update the SDL window with the latest camera frame and overlays.
 *
 * Rotates the YUV image 180° (mirror both axes), uploads it to the
 * texture, renders a semi‑transparent black bar at the bottom, draws
 * colour swatches and HSV labels for the top‑3 clusters, and displays
 * the emotion classification text.
 *
 * @param[in] yuv     Pointer to the YUYV frame data.
 * @param[in] stride  Number of bytes per row in the frame.
 * @param[in] buf_len Total length of the frame buffer.
 * @return void.
 */
static void updateDisplay(const uint8_t *yuv, int stride, size_t buf_len)
{
    if(!g_sdl_ok||!g_texture||!yuv) return;

    /* Rotate the image 180° (horizontal and vertical flip). */
    std::vector<uint8_t> rot(stride*IMG_HEIGHT, 0);
    for(int y=0; y<IMG_HEIGHT; ++y) {
        for(int x=0; x<IMG_WIDTH; ++x) {
            int sx = IMG_WIDTH - 1 - x;
            int sy = IMG_HEIGHT - 1 - y;
            size_t src_offset = sy * stride + sx * 2;
            size_t dst_offset = y * stride + x * 2;
            if (src_offset + 4 > buf_len) continue;
            rot[dst_offset]   = yuv[src_offset];
            rot[dst_offset+1] = yuv[src_offset+1];
            rot[dst_offset+2] = yuv[src_offset+2];
            rot[dst_offset+3] = yuv[src_offset+3];
        }
    }

    SDL_UpdateTexture(g_texture, NULL, rot.data(), stride);
    SDL_RenderClear(g_renderer);
    SDL_RenderCopy(g_renderer, g_texture, NULL, NULL);

    if(g_font){
        int bar_h=140, bar_y=IMG_HEIGHT-bar_h;
        SDL_SetRenderDrawBlendMode(g_renderer,SDL_BLENDMODE_BLEND);
        SDL_SetRenderDrawColor(g_renderer,0,0,0,190);
        SDL_Rect bar={0,bar_y,IMG_WIDTH,bar_h};
        SDL_RenderFillRect(g_renderer,&bar);

        int n=g_top_count.load();
        SDL_Color w={255,255,255,255}; char line[64];
        for(int i=0;i<n;++i){
            int h=g_top_h[i],s=g_top_s[i],v=g_top_v[i];
            float ratio = g_top_ratio[i].load();
            SDL_Rect sw={6,bar_y+6+i*19,15,15};
            SDL_SetRenderDrawColor(g_renderer,(h*255)/H_BINS,(s*255)/S_BINS,(v*255)/V_BINS,220);
            SDL_RenderFillRect(g_renderer,&sw);
            snprintf(line,sizeof(line),"#%d: H=%d S=%d V=%d R=%.2f",i+1,h,s,v,ratio);
            SDL_Surface*t=TTF_RenderText_Blended(g_font,line,w);
            if(t){
                SDL_Texture*tx=SDL_CreateTextureFromSurface(g_renderer,t);
                SDL_Rect dst = {25, bar_y+6+i*19, t->w, t->h};
                SDL_RenderCopy(g_renderer,tx,NULL,&dst);
                SDL_DestroyTexture(tx);SDL_FreeSurface(t);
            }
        }

        // Display emotion label as text (instead of integer)
        // Take a snapshot of the current emotion string and confidence
        char emotion_text[128];
        {
            std::lock_guard<std::mutex> lock(g_emotion_mutex);
            snprintf(emotion_text, sizeof(emotion_text), "Emotion: %s (%.1f%%)",
                     g_emotion_label_str[0] ? g_emotion_label_str : "None",
                     g_emotion_conf_val * 100);
        }
        SDL_Surface*t=TTF_RenderText_Blended(g_font, emotion_text, w);
        if(t){
            SDL_Texture*tx=SDL_CreateTextureFromSurface(g_renderer,t);
            SDL_Rect dst = {6, bar_y+bar_h-28, t->w, t->h};
            SDL_RenderCopy(g_renderer,tx,NULL,&dst);
            SDL_DestroyTexture(tx);SDL_FreeSurface(t);
        }
    }
    SDL_RenderPresent(g_renderer);
    SDL_Event e; while(SDL_PollEvent(&e)){}
}
