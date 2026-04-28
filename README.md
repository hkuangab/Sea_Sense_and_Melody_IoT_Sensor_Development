# Sea-Sense-and-Melody---IoT-Sensor-Development
UROP 1100R Repository

# I. Project Background
This project is developed based on Raspberry Pi 5. The core objective is to collect environmental data through various sensors, combine data processing, color mapping, and large-scale model interaction to associate environmental states with "mood" tags, ultimately providing end-users with visualized data and mood descriptions. Future development will include a GUI interface and more functional modules.

Core Logic: Data is collected using cameras and various environmental sensors (light, sound, rain, humidity, etc.). Based on subtle differences in sensor voltage, hexadecimal color codes are assigned, mapping to corresponding "moods," and data statistics, visualization, and large-scale model interaction are completed.

# II. Implemented Functions (Taking a Light Sensor as an Example)

## 1. Data and Emotion Association Logic: 
The `light_intensity` value is inversely proportional to `brightness` (a larger value → darker environment → more negative emotion, and vice versa); combining the absolute value of `light_intensity` (data converted by MCP3008) and its degree of change (emotional stability), the system assigns a "mood" tag (the key in the mapping dictionary) and randomly extracts a hexadecimal color number from the corresponding value.

## 2. Data Storage and Output: 
Raw data collected by sensors is written to an Excel spreadsheet, and statistical results are output to the console.

## 3. Data Visualization: 
Three types of statistical charts are generated: a line chart of light intensity, a bar chart of emotion categories, and a pie chart showing the percentage of each emotion.

## 4. Large Model Interaction and Terminal Feedback: 
Items with similar color codes are grouped together, and labels are English words related to "mood." The processed data is then fed into the Moondream and Deepseek large models to generate mood descriptions, which are then returned to the end-user page (a GUI interface will be developed to optimize the display later).

# III. Existing Shortcomings and Areas for Optimization

## 1. Limited Sensor Coverage: 
Currently, the research and implementation focus only on photosensors. Although there are plans to expand to raindrop, sound, and temperature sensors, multi-sensor collaborative data acquisition has not yet been completed.

## 2. Insufficient Sensor Sensitivity Control: 
Subtle environmental changes can cause excessive fluctuations in the collected data, affecting the accuracy of emotion mapping.

## 3. Insufficient Input Signal Strength: 
An integrated module (such as a CD4007 series CMOS or operational amplifier circuit) needs to be introduced to amplify small AC signals and improve data acquisition accuracy.

## 4. Lack of Data Prediction Capability: 
Consider introducing an LSTM model to predict emotions and environmental data based on sequence data.

## 5. Camera Functionality Not Yet Implemented: 
Future plans include integrating a YOLO model to recognize facial expressions or objects, enriching the data sources for emotion mapping.

## 6. Low Data Storage Efficiency: 
Multiple sensors cannot be concurrently written to Excel. Future plans include replacing it with a MySQL database to optimize data management and concurrent processing capabilities.

# IV. Project Summary (IoT Development Perspective)

## 1. Project Advantages

- Clear Demand Positioning and Strong Scenario Applicability: Based on Raspberry Pi 5, combined with common sensors and large models, environmental data is associated with "mood" tags, creating scenarios close to daily life (such as smart home emotion linkage and environmental sensing terminals), possessing practical application value.

- Complete Hardware-Software Collaboration Logic: From low-level sensor data acquisition (MCP3008 conversion), to mid-level data processing, color mapping, storage and statistics, and then to high-level large-scale model interaction and terminal feedback, a complete hardware-software chain is formed, conforming to the core architecture of IoT projects: "sensing-transmission-processing-feedback".

- Strong Scalability: Optimization directions are reserved for multi-sensor integration, camera YOLO recognition, LSTM prediction, and database replacement, which can be gradually improved later to enhance project complexity and practicality.

- Technology Stack Aligned with IoT Development Trends: Integrating embedded development (Raspberry Pi), sensor applications, data visualization, and large-scale model interaction, it balances low-level hardware operation and high-level software applications, aligning with the current development trend of IoT and AI integration.

## 2. Core Issues to be Resolved (Hardware-Software Collaboration Perspective)

- Hardware Level: Signal amplification and sensor sensitivity calibration are key—the current weak input signal and large data fluctuations are essentially due to insufficient optimization in hardware selection and circuit design. Priority should be given to solving the integration module access and sensor calibration issues to provide a stable data source for high-level data processing (the foundation of hardware-software collaboration is "accurate perception").

- Software Level: Data storage and concurrent processing are bottlenecks—Excel cannot support concurrent writes from multiple sensors, requiring a rapid migration to MySQL. Simultaneously, data read/write logic needs optimization to prevent data loss or corruption. Furthermore, the integration of LSTM prediction and YOLO recognition requires careful adaptation of the algorithms to the underlying hardware (e.g., Raspberry Pi computing power optimization).

- Collaboration Level: A clear data synchronization mechanism for multiple sensors is needed to avoid data conflicts between different sensors. Simultaneously, optimization of latency in large model interactions (due to limited Raspberry Pi computing power) is crucial. A balance between data processing accuracy and response speed is needed to ensure smooth terminal feedback.

## 3. Project Outlook
The core value of this project lies in the closed loop of "environmental perception → emotion mapping → intelligent feedback." If the above optimization points can be resolved, it can be expanded to multiple scenarios: smart homes (adjusting lighting and music based on environmental mood), environmental monitoring terminals (combining emotion tags to assist scene adaptation), and personal health assistance (providing comfortable environment suggestions through the association between environment and emotion).

From a hardware/software synergy perspective, future efforts should focus on promoting "hardware standardization" (sensor module integration, circuit standardization) and "software modularization" (separating data processing, visualization, and large model interaction into independent modules) to improve project maintainability and scalability. Simultaneously, leveraging the Raspberry Pi's open-source ecosystem can introduce more third-party tools, reducing development costs and accelerating feature deployment.

# V. Development Environment and Core Dependencies

## 1. Hardware Environment

- Core Controller: Raspberry Pi 5 (4GB/8GB version, 8GB recommended to support lightweight operation of large models)

- Compatible Sensors: Photosensitive sensor (GL5516 model recommended, adjustable sensitivity)

- Data Conversion Module: MCP3008 (8-channel 10-bit ADC, used to convert analog signals from sensors to digital signals, compatible with Raspberry Pi GPIO ports)

- Auxiliary Hardware: Breadboard, DuPont wires (male to female, male to male), 5V power adapter, SD card (32GB or higher, Class 10 recommended)

- Reserved Hardware: Rain sensor, acoustic sensor (MIC module), temperature and humidity sensor (DHT11/DHT22), USB camera (supports Raspberry Pi driver)

## 2. Software Environment

- System Version: Raspberry Pi OS (64-bit), based on Debian 12 (Bookworm)

- Programming Language: Python 3.10+ (Raspberry Pi OS comes with this version by default; requires an upgrade to the corresponding version)

- Core dependencies (installed via pip):

- Sensor data acquisition: adafruit-circuitpython-mcp3xxx (MCP3008 driver), RPi.GPIO (Raspberry Pi GPIO control)

- Data storage: pandas (Excel read/write), openpyxl (Excel format support)

- Data visualization: matplotlib (line chart, bar chart, pie chart generation)

- Large model interaction: requests (API calls, compatible with Moondream and Deepseek), transformers (optional, for lightweight local deployment of large models)

# VI. Hardware and software collaboration practical precautions
1. Hardware Wiring Specifications: The wiring between the MCP3008 and Raspberry Pi GPIO ports must strictly correspond (SCK to GPIO11, MISO to GPIO9, MOSI to GPIO10, CS to GPIO8). Connect the sensor VCC to 3.3V (avoid 5V to prevent damage to the sensor). The GND should correspond to the Raspberry Pi's GND. Connect the analog signal output to channels CH0-CH7 of the MCP3008 (CH0 is recommended for the photosensitive sensor).

2. Sensor Calibration Method: When using the photosensitive sensor for the first time, benchmark data should be collected under standard lighting conditions (such as indoor natural light or a dark environment). Adjust the threshold range of `light_intensity` in the code to reduce data fluctuations caused by subtle environmental changes.

3. Data Processing Optimization: When collecting data, a "moving average filter" logic can be added (taking the average of 5-10 consecutive collections) to reduce data noise and improve the stability of mood mapping. The color mapping dictionary can be adjusted according to actual test results to ensure that data from similar environments correspond to appropriate "mood" labels.

4. Raspberry Pi Computing Power Optimization: For large models, it is recommended to use API calls (to avoid excessive computing power consumption from local deployment). Data visualization can be set to generate on a schedule (e.g., generate statistical charts every 5 minutes) to reduce the performance consumption of Raspberry Pi due to real-time computation.

5. Debugging Techniques: During development, the Raspberry Pi can be connected via serial port or SSH to print raw sensor data, converted data, and color codes in real time, quickly locating hardware wiring errors or software logic problems. If data acquisition fails, first check the GPIO port enable status, sensor wiring, and MCP3008 driver installation.

# VII. Subsequent Development Roadmap (Phase-by-Phase)

## Phase 1: Hardware Optimization and Multi-Sensor Integration

- Complete the wiring and driver development for raindrop, acoustic, and temperature/humidity sensors to achieve synchronous data acquisition from multiple sensors.

- Connect CD4007 series CMOS modules or operational amplifier circuits to amplify small sensor input signals and calibrate sensor sensitivity.

## Phase 2: Software Upgrade and Data Management Optimization

- Replace the data storage method, migrating from Excel to MySQL to achieve concurrent writing, querying, and management of multi-sensor data.

- Optimize data processing logic, add LSTM model integration, and implement environmental data and emotion prediction functions.

## Phase 3: Functionality Expansion and Interface Development

- Integrate USB camera and YOLO model to achieve facial expression and object recognition, enriching the data source for emotion mapping.

- Develop GUI interface, integrating data visualization charts, mood descriptions, and sensor status to improve user interaction experience.

## Phase 4: Testing, Optimization, and Deployment

- Complete full-featured testing, fix hardware compatibility, software logic, and performance issues, and optimize large model interaction latency.

- Compile deployment documentation, achieve one-click project deployment (adapted to Raspberry Pi environment), upload complete code to GitHub, and provide detailed usage instructions.

# VIII. Remarks

1. This project is an open-source IoT practice project, focusing on hardware and software collaborative development and AI integration applications. Developers are welcome to fork, star, and provide optimization suggestions.

2. The code and documentation will be continuously updated, and development tasks at each stage will be advanced simultaneously. If you have any questions, please leave a message in the Issues section.

3. Hardware selections can be replaced according to actual needs (such as sensor models, ADC modules), and software dependencies need to be adjusted according to the Raspberry Pi system version to ensure compatibility.
