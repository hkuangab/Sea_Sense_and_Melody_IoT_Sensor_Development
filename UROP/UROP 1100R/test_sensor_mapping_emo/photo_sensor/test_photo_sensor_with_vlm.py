# -*- coding: utf-8 -*-
"""
Intelligent Light Emotion Analysis System with ADC Monitoring
Features: Combine light sensor and AI emotion analysis with ADC voltage tracking
1. Real-time monitoring of environmental light intensity changes
2. Record light data, voltage, and ADC values to Excel spreadsheets
3. Generate light change, voltage, and ADC analysis charts
4. Trigger AI emotion analysis through light change rate
5. Map emotions to color labels
"""

import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import os
import requests
import json
import re
import matplotlib.patches as patches
import matplotlib
import logging
import traceback
import sys
from collections import deque
import threading
import random
from datetime import datetime, timedelta
import time
from typing import List, Dict, Any, Tuple, Optional
import ollama

# Try importing gpiozero, use simulation mode if not on Raspberry Pi
try:
    from gpiozero import MCP3008
    print("gpiozero library available, starting sensor data collection")
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    print("Warning: gpiozero library not available, running in simulation mode")

# Set matplotlib to use default font
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('light_emotion.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# Global Configuration Variables
# ============================================================================

# Emotion intensity mapping
INTENSITY_MAP = {
    "extreme": 8,
    "high": 6,
    "moderate": 4,
    "low": 3,
    "very_low": 2
}

# Brightness category descriptions
BRIGHTNESS_CATEGORIES = {
    "extremely_bright": "exceptionally brilliant and radiant",
    "very_bright": "intensely luminous and dazzling",
    "bright": "vividly illuminated and gleaming",
    "moderately_bright": "pleasantly lit and shining",
    "somewhat_bright": "adequately illuminated and clear",
    "medium": "neutrally lit and balanced",
    "somewhat_dim": "faintly lit and subdued",
    "dim": "gently shadowed and muted",
    "dark": "significantly shadowed and obscure",
    "very_dark": "deeply shadowed and gloomy",
    "extremely_dark": "profoundly shadowed and somber",
    "pitch_dark": "almost completely lightless and black",
    "total_darkness": "absolutely lightless and impenetrably black"
}

# Change rate category descriptions
CHANGE_CATEGORIES = {
    "completely_stable": "absolutely unchanging and constant",
    "very_stable": "remarkably steady and unwavering",
    "stable": "consistently even and regular",
    "slightly_changing": "minimally fluctuating and varying",
    "moderately_changing": "noticeably shifting and altering",
    "changing": "actively transforming and evolving",
    "rapidly_changing": "quickly transitioning and metamorphosing",
    "very_rapidly_changing": "swiftly oscillating and undulating",
    "extremely_rapidly_changing": "violently pulsating and throbbing",
    "chaotically_changing": "wildly fluctuating and convulsing"
}

# Emotion intensity descriptions
INTENSITY_DESCRIPTIONS = {
    "extreme": "an overwhelmingly intense",
    "high": "a powerfully strong",
    "moderate": "a noticeably present",
    "low": "a subtly gentle",
    "very_low": "a faintly perceptible"
}

# Basic emotion mapping (适配100-200范围)
EMOTION_MAP = {
    "extremely_bright": "happy",         # 190+
    "very_bright": "happy",              # 180-189
    "bright": "happy",                   # 170-179
    "moderately_bright": "peaceful",     # 160-169
    "somewhat_bright": "neutral",        # 150-159
    "medium": "neutral",                 # 140-149
    "somewhat_dim": "thoughtful",        # 130-139
    "dim": "sad",                        # 120-129
    "dark": "sad",                       # 110-119
    "very_dark": "fearful",              # 100-109
    "extremely_dark": "fearful",         # 90-99
    "pitch_dark": "fearful",             # 80-89
    "total_darkness": "fearful"          # <80
}

# Explanation text templates
EXPLANATION_TEMPLATES = [
    "The lighting is {brightness_desc} with a {change_desc} pattern, "
    "suggesting {intensity_desc} {emotion} emotional state.",
    
    "With {brightness_desc} illumination and {change_desc} dynamics, "
    "the atmosphere conveys {intensity_desc} sense of {emotion}.",
    
    "The {brightness_desc} environment coupled with {change_desc} light "
    "creates {intensity_desc} {emotion} mood.",
    
    "Characterized by {brightness_desc} brightness and {change_desc} fluctuations, "
    "the scene evokes {intensity_desc} feeling of {emotion}.",
    
    "The combination of {brightness_desc} lighting and {change_desc} changes "
    "produces {intensity_desc} {emotion} emotional response."
]

# Rich emotion keyword mapping
EMOTION_KEYWORD_MAP = {
    "happy": ["happy", "joyful", "cheerful", "excited", "content", "smiling", "delighted"],
    "sad": ["sad", "depressed", "unhappy", "sorrowful", "melancholy", "crying", "gloomy"],
    "angry": ["angry", "furious", "irritated", "annoyed", "rage", "frustrated", "enraged"],
    "neutral": ["neutral", "calm", "relaxed", "peaceful", "serene", "quiet", "tranquil"],
    "surprised": ["surprised", "shocked", "amazed", "astonished", "startled", "astounded"],
    "fearful": ["fearful", "scared", "afraid", "terrified", "anxious", "nervous", "frightened"],
    "loving": ["loving", "affectionate", "caring", "tender", "romantic", "adoring", "devoted"],
    "peaceful": ["peaceful", "tranquil", "serene", "calm", "placid", "untroubled", "undisturbed"],
    "energetic": ["energetic", "dynamic", "vigorous", "robust", "strenuous", "forceful", "powerful"],
    "thoughtful": ["thoughtful", "contemplative", "reflective", "meditative", "pensive", "ruminative"],
    "hopeful": ["hopeful", "optimistic", "sanguine", "confident", "assured", "certain", "positive"],
    "nostalgic": ["nostalgic", "reminiscent", "retrospective", "backward-looking", "yearning", "longing"],
    "curious": ["curious", "inquisitive", "inquiring", "questioning", "probing", "searching"],
    "confident": ["confident", "self-assured", "self-confident", "self-reliant", "self-sufficient"],
    "playful": ["playful", "frolicsome", "sportive", "gamesome", "rollicking", "romping", "gamboling"]
}

# Color palette
COLOR_PALETTE = {
    "happy": ["#FFFF00", "#FFD700", "#FFEC00", "#FFF700", "#FFFA00"],
    "sad": ["#4169E1", "#4682B4", "#5F9EA0", "#6495ED", "#6A5ACD"],
    "angry": ["#FF0000", "#DC143C", "#B22222", "#8B0000", "#800000"],
    "neutral": ["#C0C0C0", "#A9A9A9", "#808080", "#696969", "#778899"],
    "surprised": ["#FFA500", "#FF8C00", "#FF7F50", "#FF6347", "#FF4500"],
    "fearful": ["#800080", "#4B0082", "#483D8B", "#6A5ACD", "#7B68EE"],
    "loving": ["#FF69B4", "#FF1493", "#FF00FF", "#FF00CC", "#FF0099"],
    "peaceful": ["#87CEEB", "#87CEFA", "#00BFFF", "#1E90FF", "#4169E1"],
    "energetic": ["#FF4500", "#FF8C00", "#FFA500", "#FFD700", "#FFFF00"],
    "thoughtful": ["#708090", "#778899", "#B0C4DE", "#D3D3D3", "#DCDCDC"],
    "hopeful": ["#00FFFF", "#00CED1", "#40E0D0", "#48D1CC", "#20B2AA"],
    "nostalgic": ["#DAA520", "#B8860B", "#BC8F8F", "#CD853F", "#D2691E"],
    "curious": ["#9400D3", "#8A2BE2", "#9370DB", "#6A5ACD", "#483D8B"],
    "confident": ["#FFD700", "#FFEC00", "#FFF700", "#FFFA00", "#FFFD00"],
    "playful": ["#FF00FF", "#FF00CC", "#FF0099", "#FF0066", "#FF0033"]
}

# ============================================================================
# Configuration Class
# ============================================================================
class SystemConfig:
    """System configuration parameters"""
    def __init__(self):
        # Data saving configuration
        self.DATA_FILE = os.path.join(os.path.dirname(__file__), "light_emotion_analysis.xlsx")
        self.CHART_FILE = os.path.join(os.path.dirname(__file__), "light_emotion_analysis.png")
        
        # Sensor configuration
        self.SENSOR_CHANNEL = 0
        self.SAMPLE_INTERVAL = 1.0
        self.LIGHT_THRESHOLD = 30
        self.HISTORY_SIZE = 5
        
        # ADC configuration
        self.ADC_RESOLUTION = 1023  # 10-bit ADC
        self.ADC_REF_VOLTAGE = 3.3  # 3.3V reference voltage
        
        # AI service configuration
        self.OLLAMA_HOST = "localhost"
        self.OLLAMA_PORT = 11434
        self.VISION_MODEL = "moondream"
        self.TEXT_MODEL = "deepseek-r1:1.5b"
        
        # Batch processing configuration
        self.BATCH_SIZE = 10
        self.MAX_QUEUE_SIZE = 50
        
        # Operation configuration
        self.DEFAULT_DURATION = 300
        self.SAVE_INTERVAL = 20

# ============================================================================
# Light Sensor Class
# ============================================================================
class LightSensor:
    def __init__(self, channel=0, history_size=5, simulate=False, config=None):
        """Initialize photosensitive sensor"""
        self.simulate = simulate or not GPIOZERO_AVAILABLE
        self.light_history = []
        self.history_size = history_size
        self.config = config or SystemConfig()
        
        if not self.simulate:
            try:
                self.sensor = MCP3008(channel=channel)
                logger.info(f"Light sensor initialized on channel {channel}")
                self.simulate = False
            except Exception as e:
                logger.error(f"Failed to initialize light sensor: {e}")
                self.sensor = None
                self.simulate = True
        else:
            self.sensor = None
            logger.info("Running in simulation mode")
    
    def read_light_intensity(self) -> Tuple[int, float, float]:
        """Read light intensity (0-255) and return (light_value, raw_adc, voltage)"""
        try:
            if self.simulate or self.sensor is None:
                # Simulation mode: Generate random but reasonable light values
                # 模拟放大器后的范围 100-200
                raw_adc = random.uniform(400, 800)  # 模拟10位ADC原始值
                # 将ADC值映射到0-255范围
                light_value = int(self.MAP(raw_adc, 400, 800, 100, 200))
                # 计算电压
                voltage = (raw_adc / self.config.ADC_RESOLUTION) * self.config.ADC_REF_VOLTAGE
            else:
                # Real sensor mode
                raw_adc = self.sensor.raw_value  # 读取原始ADC值 (0-1023)
                # 将ADC值映射到0-255范围
                light_value = int(self.MAP(raw_adc, 0, self.config.ADC_RESOLUTION, 0, 255))
                # 计算电压
                voltage = (raw_adc / self.config.ADC_RESOLUTION) * self.config.ADC_REF_VOLTAGE
            return light_value, raw_adc, voltage
        except Exception as e:
            logger.error(f"Error reading light sensor: {e}")
            return 0, 0, 0.0
    
    def MAP(self, x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
        """Value mapping function"""
        try:
            return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
        except ZeroDivisionError:
            return out_min
    
    def calculate_light_change(self, current_value: float) -> float:
        """Calculate light change"""
        self.light_history.append(current_value)
        if len(self.light_history) > self.history_size:
            self.light_history.pop(0)
        
        if len(self.light_history) >= 2:
            historical_mean = np.mean(self.light_history[:-1])
            change = abs(current_value - historical_mean)
            return float(change)
        return 0.0
    
    def close(self):
        """Close sensor resources"""
        if not self.simulate and self.sensor is not None:
            self.sensor.close()
            logger.info("Light sensor closed")

# ============================================================================
# Emotion Analyzer Class
# ============================================================================
class EmotionAnalyzer:
    def __init__(self, config: SystemConfig):
        """Initialize emotion analyzer"""
        self.config = config
        self.base_url = f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}"
        self.is_available = False
        self.last_check_time = 0
        self.check_interval = 30
        self.check_ollama_status()
    
    def check_ollama_status(self, force_check=False) -> bool:
        """Check Ollama service status"""
        current_time = time.time()
        if not force_check and (current_time - self.last_check_time < self.check_interval):
            return self.is_available
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.is_available = True
                logger.info("Ollama service is running")
            else:
                self.is_available = False
                logger.warning(f"Ollama service returned status {response.status_code}")
        except Exception as e:
            self.is_available = False
            logger.warning(f"Ollama service unavailable: {e}")
        
        self.last_check_time = current_time
        return self.is_available
    
    def _categorize_brightness(self, brightness: int) -> tuple[str, str]:
        """Categorize brightness level (范围: 100-200)"""
        if brightness >= 190:  # 非常明亮
            return "extremely_bright", BRIGHTNESS_CATEGORIES["extremely_bright"]
        elif brightness >= 180:
            return "very_bright", BRIGHTNESS_CATEGORIES["very_bright"]
        elif brightness >= 170:
            return "bright", BRIGHTNESS_CATEGORIES["bright"]
        elif brightness >= 160:
            return "moderately_bright", BRIGHTNESS_CATEGORIES["moderately_bright"]
        elif brightness >= 150:
            return "somewhat_bright", BRIGHTNESS_CATEGORIES["somewhat_bright"]
        elif brightness >= 140:
            return "medium", BRIGHTNESS_CATEGORIES["medium"]
        elif brightness >= 130:
            return "somewhat_dim", BRIGHTNESS_CATEGORIES["somewhat_dim"]
        elif brightness >= 120:
            return "dim", BRIGHTNESS_CATEGORIES["dim"]
        elif brightness >= 110:
            return "dark", BRIGHTNESS_CATEGORIES["dark"]
        elif brightness >= 100:
            return "very_dark", BRIGHTNESS_CATEGORIES["very_dark"]
        elif brightness >= 90:
            return "extremely_dark", BRIGHTNESS_CATEGORIES["extremely_dark"]
        elif brightness >= 80:
            return "pitch_dark", BRIGHTNESS_CATEGORIES["pitch_dark"]
        else:
            return "total_darkness", BRIGHTNESS_CATEGORIES["total_darkness"]
    
    def _categorize_change(self, light_change: float) -> tuple[str, str]:
        """Categorize change level"""
        if light_change < 2:
            return "completely_stable", CHANGE_CATEGORIES["completely_stable"]
        elif light_change < 5:
            return "very_stable", CHANGE_CATEGORIES["very_stable"]
        elif light_change < 10:
            return "stable", CHANGE_CATEGORIES["stable"]
        elif light_change < 20:
            return "slightly_changing", CHANGE_CATEGORIES["slightly_changing"]
        elif light_change < 40:
            return "moderately_changing", CHANGE_CATEGORIES["moderately_changing"]
        elif light_change < 60:
            return "changing", CHANGE_CATEGORIES["changing"]
        elif light_change < 80:
            return "rapidly_changing", CHANGE_CATEGORIES["rapidly_changing"]
        elif light_change < 100:
            return "very_rapidly_changing", CHANGE_CATEGORIES["very_rapidly_changing"]
        elif light_change < 150:
            return "extremely_rapidly_changing", CHANGE_CATEGORIES["extremely_rapidly_changing"]
        else:
            return "chaotically_changing", CHANGE_CATEGORIES["chaotically_changing"]
    
    def _select_color(self, emotion: str) -> str:
        """Select color"""
        color_list = COLOR_PALETTE.get(emotion)
        if color_list and len(color_list) > 0:
            return random.choice(color_list)
        logger.warning(f"Emotion '{emotion}' not found in color palette, using default color")
        return "#808080"
    
    def _select_emotion_keywords(self, emotion: str, intensity: str) -> List[str]:
        """Select emotion keywords"""
        all_keywords = EMOTION_KEYWORD_MAP.get(emotion, [emotion])
        num_keywords = INTENSITY_MAP.get(intensity, 3)
        num_keywords = min(num_keywords, len(all_keywords))
        
        if len(all_keywords) > num_keywords:
            return random.sample(all_keywords, num_keywords)
        return all_keywords

    def _determine_emotion(self, brightness_category: str, change_category: str, 
                      brightness: int, light_change: float) -> dict[str, any]:
        """根据亮度和变化率确定情感"""
        base_emotion = EMOTION_MAP.get(brightness_category, "neutral")
        
        if "chaotically" in change_category or "extremely_rapidly" in change_category:
            if brightness >= 170:  # 170+ 对应原180+
                adjusted_emotion = "surprised"
                intensity = "extreme"
            elif brightness >= 140:  # 140-169 对应原120-179
                adjusted_emotion = "surprised"
                intensity = "high"
            else:  # <140
                adjusted_emotion = "fearful"
                intensity = "extreme"
        elif "very_rapidly" in change_category or "rapidly" in change_category:
            if brightness >= 170:  # 170+ 对应原200+
                adjusted_emotion = "energetic"
                intensity = "high"
            elif brightness >= 150:  # 150-169 对应原150-199
                adjusted_emotion = "surprised"
                intensity = "moderate"
            else:  # <150
                adjusted_emotion = "fearful"
                intensity = "high"
        elif "changing" in change_category or "moderately_changing" in change_category:
            if brightness >= 170:  # 170+ 对应原180+
                adjusted_emotion = "playful" if random.random() > 0.5 else "curious"
                intensity = "moderate"
            elif brightness >= 140:  # 140-169 对应原120-179
                adjusted_emotion = "thoughtful"
                intensity = "low"
            else:  # <140
                adjusted_emotion = "nostalgic"
                intensity = "moderate"
        elif "slightly_changing" in change_category:
            if brightness >= 170:  # 170+ 对应原200+
                adjusted_emotion = "confident"
                intensity = "low"
            elif brightness >= 150:  # 150-169
                adjusted_emotion = base_emotion
                intensity = "very_low"
            else:  # <150
                adjusted_emotion = "thoughtful"
                intensity = "low"
        else:  # 稳定状态
            if brightness >= 180:  # 180+ 对应原220+
                adjusted_emotion = "happy"
                intensity = "high"
            elif brightness >= 160:  # 160-179 对应原180-219
                adjusted_emotion = "peaceful"
                intensity = "moderate"
            elif brightness >= 140:  # 140-159
                adjusted_emotion = "neutral"
                intensity = "very_low"
            elif brightness >= 120:  # 120-139
                adjusted_emotion = "thoughtful"
                intensity = "low"
            elif brightness >= 100:  # 100-119
                adjusted_emotion = "sad"
                intensity = "moderate"
            else:  # <100
                adjusted_emotion = "fearful"
                intensity = "high"
        
        return {
            "primary_emotion": adjusted_emotion,
            "emotional_intensity": intensity
        }
    
    def analyze_light_data(self, light_intensity: int, light_change: float) -> dict[str, any]:
        """Analyze emotion from light data"""
        brightness = light_intensity
        brightness_category, brightness_desc = self._categorize_brightness(brightness)
        change_category, change_desc = self._categorize_change(light_change)
        emotion_info = self._determine_emotion(brightness_category, change_category, brightness, light_change)
        emotion_keywords = self._select_emotion_keywords(emotion_info["primary_emotion"], emotion_info["emotional_intensity"])
        color_code = self._select_color(emotion_info["primary_emotion"])
        
        # Create explanation
        intensity_desc = INTENSITY_DESCRIPTIONS.get(emotion_info["emotional_intensity"], "a")
        template = random.choice(EXPLANATION_TEMPLATES)
        explanation = template.format(
            brightness_desc=brightness_desc,
            change_desc=change_desc,
            intensity_desc=intensity_desc,
            emotion=emotion_info["primary_emotion"]
        )
        
        return {
            "primary_emotion": emotion_info["primary_emotion"],
            "emotion_keywords": ", ".join(emotion_keywords),
            "color_code": color_code,
            "explanation": explanation,
            "brightness_description": brightness_desc,
            "change_description": change_desc,
            "emotional_intensity": emotion_info["emotional_intensity"],
            "brightness_level": brightness
        }
    
    def analyze_with_ai(self, data_points: List[dict[str, any]]) -> dict[str, any]:
        """Analyze data using AI"""
        if not self.check_ollama_status():
            logger.warning("Ollama service unavailable, using rule-based analysis")
            return {"success": False, "error": "Ollama service unavailable"}
        
        try:
            # Prepare data summary
            intensities = [point["light_intensity"] for point in data_points]
            changes = [point["light_change"] for point in data_points]
            timestamps = [point["timestamp"] for point in data_points]
            
            data_summary = f"""
                            Light Data Summary:
                            - Data points: {len(data_points)}
                            - Time range: {timestamps[0]} to {timestamps[-1]}
                            - Light intensity range: {min(intensities)} to {max(intensities)} (0=brightest, 255=darkest)
                            - Average light intensity: {np.mean(intensities):.1f}
                            - Average change rate: {np.mean(changes):.2f}
                            - Brightest moment: {min(intensities)} at {timestamps[intensities.index(min(intensities))]}
                            - Darkest moment: {max(intensities)} at {timestamps[intensities.index(max(intensities))]}
                            """
            
            # Use moondream for initial analysis
            moondream_prompt = f"""
                                You are analyzing light data patterns. Here is the data summary:

                                {data_summary}

                                Based on this light data pattern, describe the emotional atmosphere and mood it might represent.
                                Consider:
                                1. How the light intensity changes over time
                                2. The stability or volatility of the lighting
                                3. The overall brightness level
                                4. What emotions such lighting conditions might evoke
                                """
            
            logger.info("Moondream is analyzing light data patterns...")
            moondream_response = ollama.chat(
                model=self.config.VISION_MODEL,
                messages=[{'role': 'user', 'content': moondream_prompt}]
            )
            moondream_analysis = moondream_response['message']['content']
            
            # Use deepseek for in-depth analysis
            deepseek_prompt = f"""
                                As an emotional psychologist, analyze the following light data and emotional assessment:

                                1. LIGHT DATA SUMMARY:
                                {data_summary}

                                2. MOONDREAM'S EMOTIONAL ASSESSMENT:
                                {moondream_analysis}

                                Based on psychological principles, provide:
                                1. Overall emotional state assessment
                                2. Primary emotions detected
                                3. Emotional stability analysis
                                4. Potential psychological implications
                                5. Recommendations for emotional regulation
                                """
                                            
            logger.info("Deepseek is performing in-depth emotion analysis...")
            deepseek_response = ollama.chat(
                model=self.config.TEXT_MODEL,
                messages=[{'role': 'user', 'content': deepseek_prompt}]
            )
            deepseek_analysis = deepseek_response['message']['content']
            
            return {
                "success": True,
                "moondream_analysis": moondream_analysis,
                "deepseek_analysis": deepseek_analysis,
                "data_summary": data_summary,
                "analysis_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {"success": False, "error": str(e)}

# ============================================================================
# Main System Class
# ============================================================================
class IntelligentLightEmotionSystem:
    def __init__(self, config: SystemConfig = None):
        """Initialize intelligent light emotion analysis system"""
        self.config = config or SystemConfig()
        self.sensor = LightSensor(
            channel=self.config.SENSOR_CHANNEL,
            history_size=self.config.HISTORY_SIZE,
            simulate=not GPIOZERO_AVAILABLE,
            config=self.config
        )
        self.analyzer = EmotionAnalyzer(self.config)
        self.data_buffer = deque(maxlen=self.config.MAX_QUEUE_SIZE)
        self.data_frame = pd.DataFrame()
        self.running = False
        self.ai_analysis_results = []
        
    def collect_data(self, duration: int = None) -> List[dict[str, any]]:
        """Collect light data"""
        if duration is None:
            duration = self.config.DEFAULT_DURATION
        
        collected_data = []
        start_time = time.time()
        sample_count = 0
        
        logger.info(f"Starting data collection, duration {duration} seconds...")
        
        try:
            while time.time() - start_time < duration:
                # Read sensor data
                light_intensity, raw_adc, voltage = self.sensor.read_light_intensity()
                light_change = self.sensor.calculate_light_change(light_intensity)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # Analyze emotion
                emotion_analysis = self.analyzer.analyze_light_data(light_intensity, light_change)
                
                # Create data point
                data_point = {
                    "timestamp": timestamp,
                    "light_intensity": light_intensity,
                    "raw_adc": round(raw_adc, 2),
                    "voltage": round(voltage, 3),
                    "light_change": round(light_change, 2),
                    "brightness": light_intensity,
                    "primary_emotion": emotion_analysis["primary_emotion"],
                    "emotion_keywords": emotion_analysis["emotion_keywords"],
                    "color_code": emotion_analysis["color_code"],
                    "emotional_intensity": emotion_analysis["emotional_intensity"],
                    "explanation": emotion_analysis["explanation"]
                }
                
                # Add to buffer
                collected_data.append(data_point)
                self.data_buffer.append(data_point)
                
                # 在控制台输出ADC信息
                print(f"Sample {sample_count+1}:")
                print(f"  Time: {timestamp}")
                print(f"  Light Intensity: {light_intensity}/255")
                print(f"  Raw ADC: {raw_adc:.2f}/1023")
                print(f"  Voltage: {voltage:.3f}V")
                print(f"  Change Rate: {light_change:.2f}")
                print(f"  Emotion: {emotion_analysis['primary_emotion']}")
                print(f"  Color: {emotion_analysis['color_code']}")
                print("-" * 50)
                
                # Note: Removed conditional AI analysis triggering code
                # Now AI analysis is only manually triggered after data collection
                
                # Data saving condition
                if len(collected_data) % self.config.SAVE_INTERVAL == 0:
                    self._save_data(collected_data)
                
                sample_count += 1
                logger.info(f"Sample {sample_count}: Light intensity={light_intensity}, ADC={raw_adc:.2f}, Voltage={voltage:.3f}V, Change rate={light_change:.2f}, Emotion={emotion_analysis['primary_emotion']}")
                
                time.sleep(self.config.SAMPLE_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Data collection interrupted by user")
        except Exception as e:
            logger.error(f"Error during data collection: {e}")
        
        return collected_data
    
    def run_ai_analysis_after_collection(self, collected_data: List[dict[str, any]] = None) -> dict[str, any]:
        """Run AI analysis after data collection is complete"""
        try:
            if collected_data is None:
                if len(self.data_buffer) == 0:
                    logger.warning("No data available for analysis")
                    return {"success": False, "error": "No data available for analysis"}
                data_to_analyze = list(self.data_buffer)
            else:
                data_to_analyze = collected_data
            
            logger.info(f"Starting AI analysis, analyzing {len(data_to_analyze)} data points...")
            
            ai_result = self.analyzer.analyze_with_ai(data_to_analyze)
            if ai_result["success"]:
                ai_result["trigger_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                ai_result["data_points_analyzed"] = len(data_to_analyze)
                self.ai_analysis_results.append(ai_result)
                logger.info("AI analysis completed successfully")
                
                # Print AI analysis results
                self._print_ai_analysis(ai_result)
            else:
                logger.warning(f"AI analysis failed: {ai_result.get('error', 'Unknown error')}")
                
            return ai_result
                    
        except Exception as e:
            logger.error(f"Error running AI analysis: {e}")
            return {"success": False, "error": str(e)}
    
    def _print_ai_analysis(self, ai_result: dict[str, any]):
        """Print AI analysis results"""
        print("\n" + "="*100)
        print("AI Emotion Analysis Results")
        print("="*100)
        print(f"\nAnalysis time: {ai_result.get('analysis_time', 'N/A')}")
        print(f"Data points analyzed: {ai_result.get('data_points_analyzed', 0)}")
        
        print("\n" + "-"*100)
        print("MOONDREAM Analysis (Visual Emotion Assessment):")
        print("-"*100)
        print(ai_result.get('moondream_analysis', 'No analysis available'))
        
        print("\n" + "-"*100)
        print("DEEPSEEK Analysis (Psychological Assessment):")
        print("-"*100)
        print(ai_result.get('deepseek_analysis', 'No analysis available'))
        
        print("\n" + "-"*100)
        print("Data Summary:")
        print("-"*100)
        print(ai_result.get('data_summary', 'No summary available'))
        print("\n" + "="*100)
    
    def _save_data(self, data: List[dict[str, any]]):
        """Save data to Excel"""
        try:
            if not data:
                return
            
            # Convert to DataFrame
            df_new = pd.DataFrame(data)
            
            # Merge into main DataFrame
            if self.data_frame.empty:
                self.data_frame = df_new
            else:
                self.data_frame = pd.concat([self.data_frame, df_new], ignore_index=True)
            
            # Save to Excel
            self.data_frame.to_excel(self.config.DATA_FILE, index=False)
            logger.info(f"Data saved to {self.config.DATA_FILE} ({len(self.data_frame)} records)")
            
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def generate_chart(self):
        """Generate light change charts with ADC and voltage data"""
        if self.data_frame.empty:
            logger.warning("No data available to generate charts")
            return
        
        try:
            fig, axes = plt.subplots(3, 2, figsize=(15, 15))
            fig.suptitle('Light Emotion Analysis Results with ADC Monitoring', fontsize=16, fontweight='bold')
            
            # 1. Light intensity over time
            ax1 = axes[0, 0]
            ax1.plot(self.data_frame.index, self.data_frame['light_intensity'], 
                    'b-', linewidth=2, alpha=0.7, label='Light Intensity')
            ax1.set_xlabel('Sample Index')
            ax1.set_ylabel('Light Intensity (0-255)')
            ax1.set_title('Light Intensity Over Time')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 2. Light change rate
            ax2 = axes[0, 1]
            ax2.bar(self.data_frame.index, self.data_frame['light_change'], 
                   color='orange', alpha=0.7, label='Change Rate')
            ax2.set_xlabel('Sample Index')
            ax2.set_ylabel('Light Change Rate')
            ax2.set_title('Light Change Rate')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # 3. Raw ADC value over time
            ax3 = axes[1, 0]
            ax3.plot(self.data_frame.index, self.data_frame['raw_adc'], 
                    'g-', linewidth=2, alpha=0.7, label='Raw ADC Value')
            ax3.set_xlabel('Sample Index')
            ax3.set_ylabel('Raw ADC Value (0-1023)')
            ax3.set_title('Raw ADC Value Over Time')
            ax3.grid(True, alpha=0.3)
            ax3.legend()
            
            # 4. Voltage over time
            ax4 = axes[1, 1]
            ax4.plot(self.data_frame.index, self.data_frame['voltage'], 
                    'r-', linewidth=2, alpha=0.7, label='Voltage')
            ax4.set_xlabel('Sample Index')
            ax4.set_ylabel('Voltage (V)')
            ax4.set_title('Voltage Over Time')
            ax4.grid(True, alpha=0.3)
            ax4.legend()
            
            # 5. Emotion distribution
            ax5 = axes[2, 0]
            emotion_counts = self.data_frame['primary_emotion'].value_counts()
            colors = [self.analyzer._select_color(emotion) for emotion in emotion_counts.index]
            ax5.pie(emotion_counts.values, labels=emotion_counts.index, colors=colors,
                   autopct='%1.1f%%', startangle=90)
            ax5.set_title('Emotion Distribution')
            
            # 6. Emotion color mapping
            ax6 = axes[2, 1]
            ax6.set_title('Emotion Color Mapping')
            ax6.axis('off')
            
            # Display color labels
            unique_emotions = self.data_frame['primary_emotion'].unique()
            y_position = 0.9
            
            for emotion in unique_emotions:
                color = self.analyzer._select_color(emotion)
                count = (self.data_frame['primary_emotion'] == emotion).sum()
                
                # Create color square
                rect = patches.Rectangle((0.1, y_position-0.05), 0.1, 0.05, 
                                       facecolor=color, edgecolor='black', linewidth=1)
                ax6.add_patch(rect)
                
                # Add text
                ax6.text(0.25, y_position, f'{emotion} ({count})', 
                        fontsize=10, verticalalignment='center')
                y_position -= 0.1
            
            plt.tight_layout()
            plt.savefig(self.config.CHART_FILE, dpi=300, bbox_inches='tight')
            logger.info(f"Chart saved to {self.config.CHART_FILE}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"Error generating chart: {e}")
    
    def run_test_analysis(self, num_samples: int = 20):
        """运行测试分析"""
        print("\n" + "="*100)
        print("Running Test Analysis (20 sample data points)")
        print("="*100)
        
        # 定义测试模式
        patterns = [
            ("gradual_increase", "Gradual Increase"),
            ("gradual_decrease", "Gradual Decrease"),
            ("sudden_drop", "Sudden Drop"),
            ("sudden_spike", "Sudden Spike"),
            ("stable_dark", "Stable Dark"),
            ("stable_bright", "Stable Bright"),
            ("fluctuating", "Fluctuating"),
            ("rapid_changes", "Rapid Changes"),
            ("periodic", "Periodic"),
            ("random", "Random")
        ]
        
        # Generate test data
        test_data = []
        base_time = datetime.now()
        
        for i in range(num_samples):
            pattern_idx = i % len(patterns)
            pattern_type, pattern_desc = patterns[pattern_idx]
            
            # Generate test data based on pattern (在100-200范围内)
            if pattern_type == "gradual_increase":
                # 在100-200范围内逐渐增加
                light_intensity = int(100 + (i * 5) % 100)  # 100-200
                light_change = 5.0 + (i * 0.5)
            elif pattern_type == "gradual_decrease":
                # 在100-200范围内逐渐减少
                light_intensity = int(200 - (i * 5) % 100)  # 200-100
                light_change = 8.0 - (i * 0.4)
            elif pattern_type == "sudden_drop":
                # 在100-200范围内突变
                light_intensity = 200 if i % 4 == 0 else 120
                light_change = 60.0 + np.random.random() * 40
            elif pattern_type == "sudden_spike":
                light_intensity = 100 if i % 5 == 0 else 180
                light_change = 50.0 + np.random.random() * 30
            elif pattern_type == "stable_dark":
                light_intensity = 120 + int(np.random.random() * 30)  # 120-150
                light_change = 2.0 + np.random.random() * 3
            elif pattern_type == "stable_bright":
                light_intensity = 180 + int(np.random.random() * 20)  # 180-200
                light_change = 1.5 + np.random.random() * 2
            elif pattern_type == "fluctuating":
                base = 150
                fluctuation = 40 * np.sin(i * 0.5)
                light_intensity = int(base + fluctuation)
                light_intensity = max(100, min(200, light_intensity))
                light_change = 20.0 + np.random.random() * 20
            elif pattern_type == "rapid_changes":
                light_intensity = 100 + int(np.random.random() * 100)  # 100-200
                light_change = 80.0 + np.random.random() * 70
            elif pattern_type == "periodic":
                period = 4
                light_intensity = int(150 + 50 * np.sin(2 * np.pi * i / period))
                light_intensity = max(100, min(200, light_intensity))
                light_change = 30.0 + 20 * abs(np.cos(2 * np.pi * i / period))
            else:
                light_intensity = 100 + int(np.random.random() * 100)  # 100-200
                light_change = np.random.random() * 100
            
            # 确保范围在100-200
            light_intensity = max(100, min(200, light_intensity))
            light_change = max(0, min(150, light_change))
            
            # 模拟ADC值 (400-800范围，对应light_intensity的100-200)
            raw_adc = 400 + (light_intensity - 100) * 4
            # 计算电压
            voltage = (raw_adc / 1023) * 3.3
            
            timestamp = (base_time + timedelta(minutes=i*5)).strftime("%Y-%m-%d %H:%M:%S")
            
            # Analyze emotion
            emotion_analysis = self.analyzer.analyze_light_data(light_intensity, light_change)
            
            data_point = {
                "id": i + 1,
                "timestamp": timestamp,
                "pattern_type": pattern_type,
                "pattern_description": pattern_desc,
                "light_intensity": light_intensity,
                "raw_adc": round(raw_adc, 2),
                "voltage": round(voltage, 3),
                "light_change": round(light_change, 2),
                "brightness": light_intensity,
                "primary_emotion": emotion_analysis["primary_emotion"],
                "emotion_keywords": emotion_analysis["emotion_keywords"],
                "color_code": emotion_analysis["color_code"],
                "emotional_intensity": emotion_analysis["emotional_intensity"],
                "explanation": emotion_analysis["explanation"]
            }
            
            test_data.append(data_point)
            
            # 输出测试数据信息
            print(f"Test Sample {i+1}:")
            print(f"  Pattern: {pattern_desc}")
            print(f"  Light Intensity: {light_intensity}/255")
            print(f"  Raw ADC: {raw_adc:.2f}/1023")
            print(f"  Voltage: {voltage:.3f}V")
            print(f"  Change Rate: {light_change:.2f}")
            print(f"  Emotion: {emotion_analysis['primary_emotion']}")
            print(f"  Color: {emotion_analysis['color_code']}")
            print("-" * 50)
        
        # Save test data
        test_df = pd.DataFrame(test_data)
        test_file = "light_emotion_test_data.xlsx"
        test_df.to_excel(test_file, index=False)
        print(f"\nTest data saved to: {test_file}")
        
        # Display test results
        self._display_test_results(test_data)
        
        # Ask user if they want to run AI analysis
        run_ai = input("\nRun AI analysis on test data? (y/n): ").strip().lower()
        if run_ai == 'y':
            # Run AI analysis
            print("\nRunning AI analysis...")
            ai_result = self.run_ai_analysis_after_collection(test_data)
            if not ai_result["success"]:
                print(f"AI analysis failed: {ai_result.get('error', 'Unknown error')}")
        
        return test_data
    
    def _display_test_results(self, test_data: List[dict[str, any]]):
        """Display test results"""
        print("\n" + "="*100)
        print("Test Data Analysis Results")
        print("="*100)
        print(f"{'ID':<4} {'Timestamp':<20} {'Pattern':<15} {'Intensity':<10} {'ADC':<10} {'Voltage':<8} {'Change':<8} {'Emotion':<15} {'Color':<10}")
        print("-"*100)
        
        for data in test_data:
            print(f"{data['id']:<4} {data['timestamp']:<20} {data['pattern_description']:<15} "
                  f"{data['light_intensity']:<10} {data['raw_adc']:<10.2f} {data['voltage']:<8.3f} "
                  f"{data['light_change']:<8.2f} {data['primary_emotion']:<15} {data['color_code']:<10}")
        
        # Statistics
        intensities = [d['light_intensity'] for d in test_data]
        adc_values = [d['raw_adc'] for d in test_data]
        voltages = [d['voltage'] for d in test_data]
        changes = [d['light_change'] for d in test_data]
        emotions = [d['primary_emotion'] for d in test_data]
        
        print("\n" + "="*100)
        print("Statistics")
        print("="*100)
        print(f"Total data points: {len(test_data)}")
        print(f"Average light intensity: {np.mean(intensities):.2f}")
        print(f"Average ADC value: {np.mean(adc_values):.2f}")
        print(f"Average voltage: {np.mean(voltages):.3f}V")
        print(f"Average change rate: {np.mean(changes):.2f}")
        print(f"Brightest moment: {min(intensities)}")
        print(f"Darkest moment: {max(intensities)}")
        
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        print("\nEmotion distribution:")
        for emotion, count in emotion_counts.items():
            percentage = (count / len(test_data)) * 100
            print(f"  {emotion}: {count} ({percentage:.1f}%)")
    
    def cleanup(self):
        """Clean up resources"""
        self.running = False
        self.sensor.close()
        logger.info("System cleanup completed")

# ============================================================================
# Main Function
# ============================================================================
def main():
    """Main function"""
    print("\n" + "="*100)
    print("Intelligent Light Emotion Analysis System with ADC Monitoring")
    print("="*100)
    print("Features:")
    print("1. Real-time monitoring of environmental light intensity")
    print("2. Monitor ADC values and voltage readings")
    print("3. Analyze emotions corresponding to light changes")
    print("4. Use AI models for in-depth emotion analysis")
    print("5. Generate data charts and reports with ADC data")
    print("="*100)
    
    # Create system instance
    config = SystemConfig()
    system = IntelligentLightEmotionSystem(config)
    
    try:
        # Option menu
        while True:
            print("\n" + "="*50)
            print("Main Menu")
            print("="*50)
            print("1. Run real-time data collection (5 minutes)")
            print("2. Run test analysis (20 samples)")
            print("3. Generate charts")
            print("4. Run AI analysis")
            print("5. Display AI analysis results")
            print("6. Exit")
            print("="*50)
            
            choice = input("Please select operation (1-6): ").strip()
            
            if choice == "1":
                # Run real-time data collection
                duration = input("Enter collection duration (seconds, default 300): ").strip()
                duration = int(duration) if duration else 300
                
                data = system.collect_data(duration)
                print(f"\nData collection completed, collected {len(data)} data points")
                system._save_data(data)
                
                # Ask if to run AI analysis
                run_ai = input("Run AI analysis on collected data? (y/n): ").strip().lower()
                if run_ai == 'y':
                    print("\nStarting AI analysis...")
                    system.run_ai_analysis_after_collection(data)
                
            elif choice == "2":
                # Run test analysis
                test_data = system.run_test_analysis(20)
                
            elif choice == "3":
                # Generate charts
                system.generate_chart()
                
            elif choice == "4":
                # Run AI analysis
                if len(system.data_buffer) > 0:
                    print(f"\nStarting AI analysis on collected {len(system.data_buffer)} data points...")
                    system.run_ai_analysis_after_collection()
                else:
                    print("No data available, please collect data first")
                    
            elif choice == "5":
                # Display AI analysis results
                if system.ai_analysis_results:
                    for i, result in enumerate(system.ai_analysis_results, 1):
                        print(f"\nAI Analysis Result #{i}:")
                        system._print_ai_analysis(result)
                else:
                    print("No AI analysis results available")
                    
            elif choice == "6":
                # Exit
                print("Exiting system...")
                break
                
            else:
                print("Invalid choice, please re-enter")
                
    except KeyboardInterrupt:
        print("\nProgram interrupted by user")
    except Exception as e:
        print(f"\nProgram error: {e}")
        traceback.print_exc()
    finally:
        system.cleanup()
        print("\nSystem closed")

if __name__ == "__main__":
    main()