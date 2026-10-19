#!/usr/bin/env python3
"""
HAAR CASCADE OBJECT DETECTION DEMO
Using Picamera2 for Raspberry Pi 5 camera input

This program demonstrates real-time object detection using Haar Cascade classifiers
with the Raspberry Pi 5 camera module via Picamera2 API.

Features:
- Real-time face, eye, smile, and full body detection
- Static image analysis
- Performance benchmarking
- Interactive toggle controls during live detection

Author: KUANG, Haozhe
Affiliation: The Hong Kong University of Science and Technology
Email: hkuangab@connect.ust.hk
"""

import cv2
import numpy as np
import time
import os
import sys

# Fix: Register pykms as the 'kms' module before Picamera2 tries to import it
import pykms
sys.modules['kms'] = pykms

# =============================================================================
# SECTION 1: Picamera2 Camera Interface
# =============================================================================
# Picamera2 is the native camera library for Raspberry Pi 5.
# It provides direct access to the camera sensor through libcamera.
# We wrap it in helper functions to simplify frame capture.
# =============================================================================

picamera = None  # Global Picamera2 instance

def init_camera(width=640, height=480):
    """
    Initialize the Picamera2 camera with specified resolution.
    
    Args:
        width: Desired frame width in pixels (default: 640)
        height: Desired frame height in pixels (default: 480)
    
    Returns:
        bool: True if camera initialized successfully, False otherwise
    
    Note:
        Uses RGB888 format internally. Frames are converted to BGR for OpenCV.
        A 0.5-second delay allows the camera sensor to stabilize after startup.
    """
    global picamera
    try:
        # Import Picamera2 inside the function to avoid import errors
        # if the library is not available
        from picamera2 import Picamera2 as P2
        
        picamera = P2()
        
        # Configure preview mode with RGB888 format
        # RGB888 means 8 bits per channel (Red, Green, Blue)
        config = picamera.create_preview_configuration(
            main={"size": (width, height), "format": "RGB888"}
        )
        picamera.configure(config)
        picamera.start()
        
        # Allow sensor to stabilize (important for consistent exposure)
        time.sleep(0.5)
        
        print(f"Camera initialized: {width}x{height}")
        return True
        
    except Exception as e:
        print(f"Camera initialization failed: {e}")
        return False


def capture_frame():
    """
    Capture a single frame from the Picamera2 camera.
    
    Returns:
        numpy.ndarray: Frame in BGR format (OpenCV standard), or None on failure
    
    Note:
        Picamera2 natively returns frames in RGB format.
        We convert to BGR because OpenCV uses BGR as its default color order.
        This conversion is necessary for correct color display in cv2.imshow().
    """
    global picamera
    if picamera is None:
        return None
    
    try:
        # Capture raw frame from camera (returns RGB format)
        frame = picamera.capture_array()
        
        # Convert RGB to BGR for OpenCV compatibility
        # OpenCV's imshow(), cvtColor(), etc. expect BGR ordering
        return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
    except Exception as e:
        print(f"Frame capture error: {e}")
        return None


def cleanup_camera():
    """
    Release the camera resources properly.
    
    Must be called when done with the camera to free up system resources.
    Safe to call multiple times (checks if picamera is None).
    """
    global picamera
    if picamera is not None:
        try:
            picamera.stop()   # Stop the camera streaming
            picamera.close()  # Close the camera device
            print("Camera released")
        except:
            pass  # Ignore cleanup errors
        picamera = None


# =============================================================================
# SECTION 2: Haar Cascade Classifier Loading
# =============================================================================
# Haar cascades are pre-trained XML files containing features for object detection.
# OpenCV uses these with the Viola-Jones algorithm for fast detection.
# We load four different cascades: face, eye, smile, and full body.
# =============================================================================

# Global cascade classifier objects
face_cascade = None      # Detects frontal faces
eye_cascade = None       # Detects eyes (usually within a face region)
smile_cascade = None     # Detects smiles (usually within a face region)
fullbody_cascade = None  # Detects full human bodies

# Path to the directory containing cascade XML files
CASCADE_DIR = "/home/hkuangab/Desktop/UROP 3200/ai_model/cascades"


def load_cascades():
    """
    Load all available Haar cascade classifiers from the cascade directory.
    
    Scans CASCADE_DIR for XML files and loads them into corresponding
    global variables. Only loads files that exist and are valid.
    
    Returns:
        bool: True if at least some cascades were loaded, False if directory missing
    
    Note:
        Non-existent or invalid XML files are skipped with a warning message.
        The program can still run with partial cascade loading.
    """
    global face_cascade, eye_cascade, smile_cascade, fullbody_cascade
    
    # Check if cascade directory exists
    if not os.path.exists(CASCADE_DIR):
        print(f"Error: Cascade directory not found: {CASCADE_DIR}")
        return False
    
    # List all XML files in the directory
    xml_files = [f for f in os.listdir(CASCADE_DIR) if f.endswith('.xml')]
    print(f"Found cascade directory: {CASCADE_DIR}")
    print(f"  Contains {len(xml_files)} XML file(s)")
    
    # Define expected cascade files and their corresponding variable names
    cascade_paths = {
        'haarcascade_frontalface_default.xml': 'face_cascade',
        'haarcascade_eye.xml': 'eye_cascade',
        'haarcascade_smile.xml': 'smile_cascade',
        'haarcascade_fullbody.xml': 'fullbody_cascade'
    }
    
    # Load each cascade file
    for filename, var_name in cascade_paths.items():
        path = os.path.join(CASCADE_DIR, filename)
        
        if os.path.exists(path):
            # Load the cascade classifier from XML file
            cascade = cv2.CascadeClassifier(path)
            
            # Check if the cascade was loaded successfully
            if not cascade.empty():
                # Assign to global variable using dictionary-like assignment
                globals()[var_name] = cascade
                print(f"Successfully loaded: {filename}")
            else:
                print(f"Warning: Failed to load: {filename}")
        else:
            print(f"Warning: File not found: {filename}")
    
    return True


# =============================================================================
# SECTION 3: Detection Utility Functions
# =============================================================================
# These helper functions encapsulate common detection operations:
# - Running detectMultiScale on a grayscale image
# - Drawing bounding boxes with labels on the output image
# =============================================================================

def detect_objects(gray_frame, cascade, scale_factor=1.3, min_neighbors=5, min_size=(30, 30)):
    """
    Detect objects in a grayscale image using a Haar cascade classifier.
    
    Args:
        gray_frame: Input grayscale image (numpy.ndarray)
        cascade: Loaded CascadeClassifier object
        scale_factor: How much the image size is reduced at each scale.
                     Lower values (e.g., 1.1) increase detection accuracy but slow down processing.
                     Higher values (e.g., 1.5) are faster but may miss objects.
        min_neighbors: Minimum number of overlapping detections needed to confirm an object.
                      Higher values reduce false positives but may miss true detections.
        min_size: Minimum object size in pixels (width, height).
                 Smaller objects are ignored to reduce false positives.
    
    Returns:
        list: List of rectangles [(x, y, w, h), ...] where each rectangle represents
              a detected object's position and size. Empty list if no objects found.
    """
    # Return empty list if cascade or image is invalid
    if cascade is None or gray_frame is None:
        return []
    
    # Perform multi-scale object detection
    # The algorithm scans the image at multiple scales to find objects of varying sizes
    return cascade.detectMultiScale(
        gray_frame,
        scaleFactor=scale_factor,
        minNeighbors=min_neighbors,
        minSize=min_size,
        flags=cv2.CASCADE_SCALE_IMAGE  # Standard scaling method
    )


def draw_detection_boxes(image, detections, color=(0, 255, 0), label=""):
    """
    Draw colored bounding boxes around detected objects with optional labels.
    
    Args:
        image: Output image to draw on (modified in-place)
        detections: List of rectangles [(x, y, w, h), ...] from detect_objects()
        color: BGR tuple for box color (default: green)
        label: Text label to display above each box (default: no label)
    
    Note:
        Modifies the input image directly for efficiency.
        Label text is drawn 5 pixels above the top-left corner of each box.
    """
    for (x, y, w, h) in detections:
        # Draw rectangle outline (thickness=2 pixels)
        cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
        
        # Add label text above the rectangle if provided
        if label:
            cv2.putText(image, label, (x, y - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)


# =============================================================================
# SECTION 4: Main Detection Functions
# =============================================================================
# Three main operational modes:
# 1. Static image detection - analyze a single image file
# 2. Real-time camera detection - live video feed with interactive controls
# 3. Performance benchmark - measure detection speed over multiple frames
# =============================================================================

def detect_from_image(image_path):
    """
    Detect objects in a static image file and display the result.
    
    Args:
        image_path: Path to the input image file
    
    Process:
        1. Load image from file
        2. Convert to grayscale for cascade detection
        3. Detect faces in the full image
        4. For each face, detect eyes within the face region
        5. Display annotated image until a key is pressed
    
    Note:
        Supports all image formats readable by OpenCV (jpg, png, etc.)
    """
    # Validate input file existence
    if not os.path.exists(image_path):
        print(f"Error: Image not found: {image_path}")
        return
    
    # Load image from disk
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image: {image_path}")
        return
    
    # Convert to grayscale (required for Haar cascade detection)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    display = img.copy()
    
    # Step 1: Detect faces in the entire image
    faces = detect_objects(gray, face_cascade)
    print(f"Detected {len(faces)} face(s)")
    draw_detection_boxes(display, faces, color=(255, 0, 0), label="Face")
    
    # Step 2: For each detected face, look for eyes within the face region
    for (x, y, w, h) in faces:
        # Extract the face region of interest (ROI)
        roi_gray = gray[y:y+h, x:x+w]
        roi_color = display[y:y+h, x:x+w]
        
        # Detect eyes within the face ROI
        eyes = detect_objects(roi_gray, eye_cascade, scale_factor=1.1, min_neighbors=3)
        draw_detection_boxes(roi_color, eyes, color=(0, 255, 0), label="Eye")
    
    # Display the annotated result
    cv2.imshow('Detection Result', display)
    print("Press any key to close...")
    cv2.waitKey(0)
    cv2.destroyAllWindows()


def detect_from_camera():
    """
    Real-time object detection from the Raspberry Pi 5 camera using Picamera2.
    
    Features:
    - Live video feed with face, eye, smile, and body detection
    - Interactive keyboard controls to toggle detectors and adjust parameters
    - Real-time FPS counter
    - Proper camera cleanup on exit (even with Ctrl+C)
    
    Controls:
        q - Quit the program
        f - Toggle face detection on/off
        e - Toggle eye detection on/off
        s - Toggle smile detection on/off
        b - Toggle body detection on/off
        + - Increase scale factor (faster but less accurate)
        - - Decrease scale factor (slower but more accurate)
    
    Note:
        The image is NOT flipped. Picamera2 returns the correct orientation.
        Previous versions used cv2.flip(frame, 1) which caused mirroring issues.
    """
    # Initialize the camera
    if not init_camera():
        print("Error: Could not initialize Picamera2")
        return
    
    print("\nStarting real-time detection...")
    print("Controls:")
    print("  'q' - Quit")
    print("  'f' - Toggle face detection")
    print("  'e' - Toggle eye detection")
    print("  's' - Toggle smile detection")
    print("  'b' - Toggle body detection")
    print("  '+' - Increase scale factor (faster, less accurate)")
    print("  '-' - Decrease scale factor (slower, more accurate)")
    
    # Detection toggle switches (all start enabled except smile and body)
    show_faces = True
    show_eyes = True
    show_smiles = False
    show_bodies = False
    
    # Initial scale factor for face/body detection
    # Higher values = faster but less accurate
    scale_factor = 1.3
    
    # FPS calculation variables
    fps_counter = 0
    fps_timer = time.time()
    fps = 0
    
    try:
        # Main processing loop
        while True:
            # Capture a frame from the camera
            frame = capture_frame()
            if frame is None:
                print("Failed to capture frame")
                break

            frame = cv2.rotate(frame, cv2.ROTATE_180)

            
            # Create copies for display and grayscale processing
            display = frame.copy()
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # ---- Face Detection ----
            if show_faces and face_cascade is not None:
                faces = detect_objects(gray, face_cascade, 
                                      scale_factor=scale_factor, 
                                      min_neighbors=5)
                draw_detection_boxes(display, faces, color=(255, 0, 0), label="Face")
                
                # For each detected face, search for eyes and smiles
                for (x, y, w, h) in faces:
                    # Extract face region for focused detection
                    roi_gray = gray[y:y+h, x:x+w]
                    roi_color = display[y:y+h, x:x+w]
                    
                    # Eye detection within face region
                    if show_eyes and eye_cascade is not None:
                        eyes = detect_objects(roi_gray, eye_cascade, 
                                             scale_factor=1.1, min_neighbors=3)
                        draw_detection_boxes(roi_color, eyes, 
                                            color=(0, 255, 0), label="Eye")
                    
                    # Smile detection within face region
                    if show_smiles and smile_cascade is not None:
                        smiles = detect_objects(roi_gray, smile_cascade, 
                                               scale_factor=1.5, min_neighbors=15)
                        draw_detection_boxes(roi_color, smiles, 
                                            color=(0, 0, 255), label="Smile")
            
            # ---- Full Body Detection ----
            if show_bodies and fullbody_cascade is not None:
                bodies = detect_objects(gray, fullbody_cascade, 
                                       scale_factor=scale_factor, 
                                       min_neighbors=3)
                draw_detection_boxes(display, bodies, 
                                    color=(255, 255, 0), label="Body")
            
            # ---- FPS Calculation ----
            fps_counter += 1
            if time.time() - fps_timer >= 1.0:
                fps = fps_counter
                fps_counter = 0
                fps_timer = time.time()
            
            # ---- Status Overlay ----
            # Display current settings and FPS on the frame
            status_lines = [
                f"FPS: {fps} | Scale: {scale_factor:.2f}",
                f"Face: {'ON' if show_faces else 'OFF'} | "
                f"Eye: {'ON' if show_eyes else 'OFF'} | "
                f"Smile: {'ON' if show_smiles else 'OFF'} | "
                f"Body: {'ON' if show_bodies else 'OFF'}",
                "Q:Quit | F:Face | E:Eye | S:Smile | B:Body | +/-:Scale"
            ]
            
            for i, text in enumerate(status_lines):
                y_pos = 20 + i * 22
                cv2.putText(display, text, (10, y_pos),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.40, (0, 200, 250), 1)
            
            # ---- Display and Keyboard Handling ----
            cv2.imshow('Real-time Object Detection - Picamera2', display)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("Quitting...")
                break
            elif key == ord('f'):
                show_faces = not show_faces
                print(f"Face detection: {'ON' if show_faces else 'OFF'}")
            elif key == ord('e'):
                show_eyes = not show_eyes
                print(f"Eye detection: {'ON' if show_eyes else 'OFF'}")
            elif key == ord('s'):
                show_smiles = not show_smiles
                print(f"Smile detection: {'ON' if show_smiles else 'OFF'}")
            elif key == ord('b'):
                show_bodies = not show_bodies
                print(f"Body detection: {'ON' if show_bodies else 'OFF'}")
            elif key == ord('+') or key == ord('='):
                scale_factor = min(2.0, scale_factor + 0.05)
                print(f"Scale factor increased to: {scale_factor:.2f}")
            elif key == ord('-') or key == ord('_'):
                scale_factor = max(1.01, scale_factor - 0.05)
                print(f"Scale factor decreased to: {scale_factor:.2f}")
    
    finally:
        # Ensure camera cleanup even if user presses Ctrl+C
        cleanup_camera()
        cv2.destroyAllWindows()
        print("Program terminated.")


def run_benchmark():
    """
    Run a performance benchmark to measure face detection speed.
    
    Captures 50 frames and measures:
    - Average detection time per frame
    - Theoretical maximum FPS based on detection speed
    
    Useful for comparing performance with different scale factors
    or cascade configurations.
    """
    print("\nRunning performance benchmark...")
    
    if not init_camera():
        print("Cannot run benchmark without camera")
        return
    
    print("Capturing 50 frames and measuring detection speed...")
    
    total_detect_time = 0
    num_frames = 50
    
    try:
        for i in range(num_frames):
            frame = capture_frame()
            if frame is None:
                continue
            
            # Convert to grayscale for detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # Measure detection time
            start = time.time()
            faces = detect_objects(gray, face_cascade)
            elapsed = time.time() - start
            total_detect_time += elapsed
            
            # Print progress every 10 frames
            if (i + 1) % 10 == 0:
                print(f"  Frame {i+1}/{num_frames} - "
                      f"{len(faces)} face(s) in {elapsed*1000:.1f}ms")
    
    finally:
        cleanup_camera()
    
    # Calculate and display results
    avg_time = total_detect_time / num_frames
    print(f"\nBenchmark Results:")
    print(f"  Total frames processed: {num_frames}")
    print(f"  Average detection time: {avg_time*1000:.1f} ms")
    print(f"  Theoretical FPS: {1/avg_time:.1f}")


# =============================================================================
# SECTION 5: User Interface and Main Program Flow
# =============================================================================
# Provides a menu-driven interface for selecting detection modes.
# Handles user input validation and graceful program termination.
# =============================================================================

def print_header():
    """
    Print the program header with author information.
    Displays a formatted banner at program startup.
    """
    print("=" * 62)
    print("HAAR CASCADE OBJECT DETECTION DEMO")
    print("-" * 42)
    print("Author: KUANG, Haozhe")
    print("Affiliation: The Hong Kong University of Science and Technology")
    print("Email: hkuangab@connect.ust.hk")
    print("=" * 58)
    print()


def print_menu():
    """
    Print the main menu showing available options and cascade status.
    Indicates which cascade classifiers are currently loaded.
    """
    print(f"\nCascade directory: {CASCADE_DIR}")
    print("\nAvailable cascade models:")
    print(f"  - Face: {'Loaded' if face_cascade is not None else 'Not loaded'}")
    print(f"  - Eye: {'Loaded' if eye_cascade is not None else 'Not loaded'}")
    print(f"  - Smile: {'Loaded' if smile_cascade is not None else 'Not loaded'}")
    print(f"  - Full Body: {'Loaded' if fullbody_cascade is not None else 'Not loaded'}")
    
    print("\nChoose an option:")
    print("  1. Detect objects in a static image")
    print("  2. Real-time detection from camera")
    print("  3. Run performance benchmark")
    print("  4. Exit")


def main():
    """
    Main program entry point.
    
    Workflow:
    1. Print program header
    2. Load all Haar cascade classifiers
    3. Display interactive menu
    4. Execute selected operation
    5. Loop until user chooses to exit
    
    Handles:
    - Invalid input (non-numeric, out of range)
    - Keyboard interrupt (Ctrl+C)
    - EOF (Ctrl+D)
    """
    print_header()
    
    # Load cascade classifiers before entering main loop
    if not load_cascades():
        print("Critical error: Could not load cascade files")
        sys.exit(1)
    
    # Main interaction loop
    while True:
        print_menu()
        
        try:
            choice = input("\nEnter your choice (1-4): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting...")
            break
        
        if choice == '1':
            # Static image detection
            image_path = input("Enter image path: ").strip()
            detect_from_image(image_path)
        
        elif choice == '2':
            # Real-time camera detection
            detect_from_camera()
        
        elif choice == '3':
            # Performance benchmark
            run_benchmark()
        
        elif choice == '4':
            print("Goodbye!")
            break
        
        else:
            print("Invalid choice. Please enter a number between 1 and 4.")


# =============================================================================
# Program Entry Point
# =============================================================================
if __name__ == "__main__":
    main()