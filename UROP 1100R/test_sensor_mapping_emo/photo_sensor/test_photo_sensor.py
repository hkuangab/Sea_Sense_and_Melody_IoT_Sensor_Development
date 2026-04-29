#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified Sensor Test Program
Only tests photoresistor readings on channel 0
"""

import time
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_channel0_only():
    """Only tests photoresistor on channel 0"""
    print("\n" + "="*60)
    print("Channel 0 Photoresistor Test")
    print("="*60)
    
    # 1. Check system environment
    print("1. Checking system environment...")
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            if 'Raspberry Pi' in model:
                print(f"   ✓ Raspberry Pi: {model.strip()}")
            else:
                print(f"   ✗ Not running on Raspberry Pi: {model}")
                return False
    except Exception as e:
        print(f"   ✗ Unable to read device information: {e}")
        return False
    
    # 2. Check SPI interface
    print("\n2. Checking SPI interface...")
    if os.path.exists("/dev/spidev0.0"):
        print("   ✓ SPI interface enabled (/dev/spidev0.0)")
    else:
        print("   ✗ SPI interface not enabled")
        print("     Please run: sudo raspi-config")
        print("     Select: Interface Options -> SPI -> Yes")
        print("     Then reboot")
        return False
    
    # 3. Check gpiozero library
    print("\n3. Checking gpiozero library...")
    try:
        from gpiozero import MCP3008
        print("   ✓ gpiozero library installed")
    except ImportError as e:
        print(f"   ✗ gpiozero library not installed: {e}")
        print("     Please run: pip3 install gpiozero")
        return False
    
    # 4. Test channel 0 sensor
    print("\n4. Testing channel 0 sensor readings...")
    sensor = None
    try:
        # Try to initialize sensor
        sensor = MCP3008(channel=0)
        time.sleep(0.1)  # Wait for initialization
        
        print("   Starting sensor data reading (20 readings, 0.5s interval):")
        print("   " + "-"*50)
        
        values = []
        for i in range(20):
            try:
                # Read raw value (0.0-1.0)
                raw_value = sensor.value
                
                # Validate range
                if raw_value < 0 or raw_value > 1:
                    print(f"   ⚠ Reading {i+1}: Raw value out of range: {raw_value:.3f}")
                else:
                    # Map to 0-255
                    mapped_value = int(raw_value * 255)
                    
                    # Determine light status
                    if mapped_value < 30:
                        status = "Very Bright"
                    elif mapped_value < 60:
                        status = "Bright"
                    elif mapped_value < 100:
                        status = "Medium"
                    elif mapped_value < 150:
                        status = "Dim"
                    elif mapped_value < 200:
                        status = "Dark"
                    else:
                        status = "Very Dark"
                    
                    print(f"   Reading {i+1:2d}: Raw={raw_value:.3f}, Intensity={mapped_value:3d}, Status: {status}")
                    values.append(mapped_value)
                
            except Exception as e:
                print(f"   ✗ Reading {i+1} failed: {e}")
            
            time.sleep(0.5)
        
        if values:
            avg_value = sum(values) / len(values)
            min_value = min(values)
            max_value = max(values)
            print("\n   " + "="*50)
            print(f"   Statistics: Average={avg_value:.1f}, Min={min_value}, Max={max_value}")
            print("   ✓ Sensor reading test completed")
            
            # Save test data
            save_test_data(values)
            
            return True
        else:
            print("   ✗ No valid data read")
            return False
            
    except Exception as e:
        print(f"   ✗ Sensor initialization failed: {e}")
        print("\n   Possible reasons:")
        print("   1. MCP3008 not correctly connected to Raspberry Pi")
        print("   2. Hardware connection issue")
        print("   3. Photoresistor circuit issue")
        return False
        
    finally:
        if sensor:
            sensor.close()

def save_test_data(values):
    """Save test data to file"""
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        filename = f"sensor_test_{timestamp}.txt"
        
        with open(filename, "w") as f:
            f.write("Channel 0 Photoresistor Test Data\n")
            f.write("="*60 + "\n")
            f.write(f"Test time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Test count: {len(values)}\n")
            f.write(f"Average: {sum(values)/len(values):.2f}\n")
            f.write(f"Minimum: {min(values)}\n")
            f.write(f"Maximum: {max(values)}\n")
            f.write("\nDetailed data:\n")
            
            for i, value in enumerate(values, 1):
                raw_value = value / 255.0
                f.write(f"{i:3d}. Raw value={raw_value:.3f}, Intensity={value:3d}\n")
        
        print(f"   Test data saved to: {filename}")
        
    except Exception as e:
        print(f"   Failed to save data: {e}")

def print_connection_diagram():
    """Print connection diagram"""
    print("\n" + "="*60)
    print("MCP3008 Connection Diagram (Channel 0 for photoresistor)")
    print("="*60)
    
    print("""
    Photoresistor connection (voltage divider circuit):
    ┌───── 3.3V (Pin 1)
    │
    ├───── Photoresistor
    │
    ├───── MCP3008 CH0 (Pin 1)
    │
    ├───── 10kΩ resistor
    │
    └───── GND (Pin 6)
    
    MCP3008 to Raspberry Pi connection:
    MCP3008 Pin 16 (VDD)  -> Pi Pin 1  (3.3V)
    MCP3008 Pin 15 (VREF) -> Pi Pin 1  (3.3V)
    MCP3008 Pin 14 (AGND) -> Pi Pin 6  (GND)
    MCP3008 Pin 13 (CLK)  -> Pi Pin 23 (SCLK/GPIO11)
    MCP3008 Pin 12 (DOUT) -> Pi Pin 21 (MISO/GPIO9)
    MCP3008 Pin 11 (DIN)  -> Pi Pin 19 (MOSI/GPIO10)
    MCP3008 Pin 10 (CS)   -> Pi Pin 24 (CE0/GPIO8)
    MCP3008 Pin 9  (DGND) -> Pi Pin 6  (GND)
    
    Pin description:
    - Photoresistor connected between 3.3V and GND
    - Divider point connected to MCP3008 CH0
    - Ensure 10kΩ resistor is used as lower divider resistor
    """)

def main():
    """Main function"""
    print("Simplified Photoresistor Test (only tests channel 0)")
    print("="*60)
    
    try:
        # Run test
        success = test_channel0_only()
        
        if not success:
            print("\n" + "="*60)
            print("Test failed, please check the following:")
            print("="*60)
            print_connection_diagram()
            
            print("\nSuggested troubleshooting steps:")
            print("1. Check MCP3008 power connection (3.3V and GND)")
            print("2. Check SPI connections (CLK, MISO, MOSI, CS)")
            print("3. Check photoresistor circuit connection")
            print("4. Use multimeter to measure voltage at divider point")
            print("5. Ensure SPI is enabled: sudo raspi-config")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()