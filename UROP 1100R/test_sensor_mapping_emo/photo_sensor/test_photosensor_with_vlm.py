# -*- coding: utf-8 -*-
"""
智能光照情感分析系统
功能：结合光敏传感器和AI情感分析
1. 实时监测环境光照强度变化
2. 记录光照数据到Excel表格
3. 生成光照变化分析图表
4. 通过光照变化率触发AI情感分析
5. 将情感映射为颜色标签
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

# 尝试导入gpiozero，如果不在Raspberry Pi上则使用模拟模式
try:
    from gpiozero import MCP3008
    GPIOZERO_AVAILABLE = True
except ImportError:
    GPIOZERO_AVAILABLE = False
    print("警告: gpiozero 库不可用，将在模拟模式下运行")

# 设置matplotlib使用默认字体
plt.rcParams['font.sans-serif'] = ['DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 配置日志
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
# 全局配置变量
# ============================================================================

# 情感强度映射
INTENSITY_MAP = {
    "extreme": 8,
    "high": 6,
    "moderate": 4,
    "low": 3,
    "very_low": 2
}

# 亮度分类描述
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

# 变化率分类描述
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

# 情绪强度描述
INTENSITY_DESCRIPTIONS = {
    "extreme": "an overwhelmingly intense",
    "high": "a powerfully strong",
    "moderate": "a noticeably present",
    "low": "a subtly gentle",
    "very_low": "a faintly perceptible"
}

# 基础情绪映射
EMOTION_MAP = {
    "extremely_bright": "happy",
    "very_bright": "happy",
    "bright": "happy",
    "moderately_bright": "peaceful",
    "somewhat_bright": "neutral",
    "medium": "neutral",
    "somewhat_dim": "thoughtful",
    "dim": "sad",
    "dark": "sad",
    "very_dark": "fearful",
    "extremely_dark": "fearful",
    "pitch_dark": "fearful",
    "total_darkness": "fearful"
}

# 解释文本模板
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

# 丰富的情绪关键词映射
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

# 颜色调色板
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
# 配置类
# ============================================================================
class SystemConfig:
    """系统配置参数"""
    def __init__(self):
        # 数据保存配置
        self.DATA_FILE = os.path.join(os.path.dirname(__file__), "light_emotion_analysis.xlsx")
        self.CHART_FILE = os.path.join(os.path.dirname(__file__), "light_emotion_analysis.png")
        
        # 传感器配置
        self.SENSOR_CHANNEL = 0
        self.SAMPLE_INTERVAL = 1.0
        self.LIGHT_THRESHOLD = 30
        self.HISTORY_SIZE = 5
        
        # AI服务配置
        self.OLLAMA_HOST = "localhost"
        self.OLLAMA_PORT = 11434
        self.VISION_MODEL = "moondream"
        self.TEXT_MODEL = "deepseek-r1:1.5b"
        
        # 批量处理配置
        self.BATCH_SIZE = 10
        self.MAX_QUEUE_SIZE = 50
        
        # 运行配置
        self.DEFAULT_DURATION = 300
        self.SAVE_INTERVAL = 20

# ============================================================================
# 光照传感器类
# ============================================================================
class LightSensor:
    def __init__(self, channel=0, history_size=5, simulate=False):
        """初始化光敏传感器"""
        self.simulate = simulate or not GPIOZERO_AVAILABLE
        self.light_history = []
        self.history_size = history_size
        
        if not self.simulate:
            try:
                self.sensor = MCP3008(channel=channel)
                logger.info(f"光敏传感器已在通道 {channel} 初始化")
            except Exception as e:
                logger.error(f"初始化光敏传感器失败: {e}")
                self.sensor = None
                self.simulate = True
        else:
            self.sensor = None
            logger.info("运行在模拟模式")
    
    def read_light_intensity(self) -> int:
        """读取光照强度（0-255）"""
        try:
            if self.simulate or self.sensor is None:
                # 模拟模式：生成随机但合理的光照值
                # 在模拟模式下，生成0-255之间的随机值
                light_value = random.randint(0, 255)
            else:
                # 真实传感器模式
                raw_value = self.sensor.value  # 读取原始模拟值(0.0-1.0)
                # 将0-1范围的模拟值映射到0-255范围
                light_value = int(self.MAP(raw_value, 0, 1, 0, 255))
            return light_value
        except Exception as e:
            logger.error(f"读取光敏传感器出错: {e}")
            return 0
    
    def MAP(self, x: float, in_min: float, in_max: float, out_min: float, out_max: float) -> float:
        """数值映射函数"""
        try:
            return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
        except ZeroDivisionError:
            return out_min
    
    def calculate_light_change(self, current_value: float) -> float:
        """计算光照变化"""
        self.light_history.append(current_value)
        if len(self.light_history) > self.history_size:
            self.light_history.pop(0)
        
        if len(self.light_history) >= 2:
            historical_mean = np.mean(self.light_history[:-1])
            change = abs(current_value - historical_mean)
            return float(change)
        return 0.0
    
    def close(self):
        """关闭传感器资源"""
        if not self.simulate and self.sensor is not None:
            self.sensor.close()
            logger.info("光敏传感器已关闭")

# ============================================================================
# 情感分析器类
# ============================================================================
class EmotionAnalyzer:
    def __init__(self, config: SystemConfig):
        """初始化情感分析器"""
        self.config = config
        self.base_url = f"http://{config.OLLAMA_HOST}:{config.OLLAMA_PORT}"
        self.is_available = False
        self.last_check_time = 0
        self.check_interval = 30
        self.check_ollama_status()
    
    def check_ollama_status(self, force_check=False) -> bool:
        """检查Ollama服务状态"""
        current_time = time.time()
        if not force_check and (current_time - self.last_check_time < self.check_interval):
            return self.is_available
        
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                self.is_available = True
                logger.info("Ollama 服务正在运行")
            else:
                self.is_available = False
                logger.warning(f"Ollama 服务返回状态 {response.status_code}")
        except Exception as e:
            self.is_available = False
            logger.warning(f"Ollama 服务不可用: {e}")
        
        self.last_check_time = current_time
        return self.is_available
    
    def _categorize_brightness(self, brightness: int) -> Tuple[str, str]:
        """分类亮度级别"""
        if brightness >= 240:
            return "extremely_bright", BRIGHTNESS_CATEGORIES["extremely_bright"]
        elif brightness >= 220:
            return "very_bright", BRIGHTNESS_CATEGORIES["very_bright"]
        elif brightness >= 200:
            return "bright", BRIGHTNESS_CATEGORIES["bright"]
        elif brightness >= 180:
            return "moderately_bright", BRIGHTNESS_CATEGORIES["moderately_bright"]
        elif brightness >= 160:
            return "somewhat_bright", BRIGHTNESS_CATEGORIES["somewhat_bright"]
        elif brightness >= 140:
            return "medium", BRIGHTNESS_CATEGORIES["medium"]
        elif brightness >= 120:
            return "somewhat_dim", BRIGHTNESS_CATEGORIES["somewhat_dim"]
        elif brightness >= 100:
            return "dim", BRIGHTNESS_CATEGORIES["dim"]
        elif brightness >= 80:
            return "dark", BRIGHTNESS_CATEGORIES["dark"]
        elif brightness >= 60:
            return "very_dark", BRIGHTNESS_CATEGORIES["very_dark"]
        elif brightness >= 40:
            return "extremely_dark", BRIGHTNESS_CATEGORIES["extremely_dark"]
        elif brightness >= 20:
            return "pitch_dark", BRIGHTNESS_CATEGORIES["pitch_dark"]
        else:
            return "total_darkness", BRIGHTNESS_CATEGORIES["total_darkness"]
    
    def _categorize_change(self, light_change: float) -> Tuple[str, str]:
        """分类变化级别"""
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
        """选择颜色"""
        color_list = COLOR_PALETTE.get(emotion)
        if color_list and len(color_list) > 0:
            return random.choice(color_list)
        logger.warning(f"情绪 '{emotion}' 在颜色调色板中未找到，使用默认颜色")
        return "#808080"
    
    def _select_emotion_keywords(self, emotion: str, intensity: str) -> List[str]:
        """选择情绪关键词"""
        all_keywords = EMOTION_KEYWORD_MAP.get(emotion, [emotion])
        num_keywords = INTENSITY_MAP.get(intensity, 3)
        num_keywords = min(num_keywords, len(all_keywords))
        
        if len(all_keywords) > num_keywords:
            return random.sample(all_keywords, num_keywords)
        return all_keywords
    
    def _determine_emotion(self, brightness_category: str, change_category: str, 
                          brightness: int, light_change: float) -> Dict[str, Any]:
        """基于亮度和变化确定情绪"""
        base_emotion = EMOTION_MAP.get(brightness_category, "neutral")
        
        if "chaotically" in change_category or "extremely_rapidly" in change_category:
            if brightness >= 180:
                adjusted_emotion = "surprised"
                intensity = "extreme"
            elif brightness >= 120:
                adjusted_emotion = "surprised"
                intensity = "high"
            else:
                adjusted_emotion = "fearful"
                intensity = "extreme"
        elif "very_rapidly" in change_category or "rapidly" in change_category:
            if brightness >= 200:
                adjusted_emotion = "energetic"
                intensity = "high"
            elif brightness >= 150:
                adjusted_emotion = "surprised"
                intensity = "moderate"
            else:
                adjusted_emotion = "fearful"
                intensity = "high"
        elif "changing" in change_category or "moderately_changing" in change_category:
            if brightness >= 180:
                adjusted_emotion = "playful" if random.random() > 0.5 else "curious"
                intensity = "moderate"
            elif brightness >= 120:
                adjusted_emotion = "thoughtful"
                intensity = "low"
            else:
                adjusted_emotion = "nostalgic"
                intensity = "moderate"
        elif "slightly_changing" in change_category:
            if brightness >= 200:
                adjusted_emotion = "confident"
                intensity = "low"
            elif brightness >= 150:
                adjusted_emotion = base_emotion
                intensity = "very_low"
            else:
                adjusted_emotion = "thoughtful"
                intensity = "low"
        else:  # 稳定
            if brightness >= 220:
                adjusted_emotion = "happy"
                intensity = "high"
            elif brightness >= 180:
                adjusted_emotion = "peaceful"
                intensity = "moderate"
            elif brightness >= 140:
                adjusted_emotion = "neutral"
                intensity = "very_low"
            elif brightness >= 100:
                adjusted_emotion = "thoughtful"
                intensity = "low"
            elif brightness >= 60:
                adjusted_emotion = "sad"
                intensity = "moderate"
            else:
                adjusted_emotion = "fearful"
                intensity = "high"
        
        return {
            "primary_emotion": adjusted_emotion,
            "emotional_intensity": intensity
        }
    
    def analyze_light_data(self, light_intensity: int, light_change: float) -> Dict[str, Any]:
        """分析光照数据的情感"""
        brightness = 255 - light_intensity
        brightness_category, brightness_desc = self._categorize_brightness(brightness)
        change_category, change_desc = self._categorize_change(light_change)
        emotion_info = self._determine_emotion(brightness_category, change_category, brightness, light_change)
        emotion_keywords = self._select_emotion_keywords(emotion_info["primary_emotion"], emotion_info["emotional_intensity"])
        color_code = self._select_color(emotion_info["primary_emotion"])
        
        # 创建解释
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
    
    def analyze_with_ai(self, data_points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """使用AI分析数据"""
        if not self.check_ollama_status():
            logger.warning("Ollama 服务不可用，使用基于规则的分析")
            return {"success": False, "error": "Ollama 服务不可用"}
        
        try:
            # 准备数据摘要
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
            
            # 使用moondream进行初步分析
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
            
            logger.info("正在使用 moondream 进行分析...")
            moondream_response = ollama.chat(
                model=self.config.VISION_MODEL,
                messages=[{'role': 'user', 'content': moondream_prompt}]
            )
            moondream_analysis = moondream_response['message']['content']
            
            # 使用deepseek进行深度分析
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
            
            logger.info("正在使用 deepseek 进行分析...")
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
            logger.error(f"AI 分析失败: {e}")
            return {"success": False, "error": str(e)}

# ============================================================================
# 主系统类
# ============================================================================
class IntelligentLightEmotionSystem:
    def __init__(self, config: SystemConfig = None):
        """初始化智能光照情感分析系统"""
        self.config = config or SystemConfig()
        self.sensor = LightSensor(
            channel=self.config.SENSOR_CHANNEL,
            history_size=self.config.HISTORY_SIZE,
            simulate=not GPIOZERO_AVAILABLE
        )
        self.analyzer = EmotionAnalyzer(self.config)
        self.data_buffer = deque(maxlen=self.config.MAX_QUEUE_SIZE)
        self.data_frame = pd.DataFrame()
        self.running = False
        self.ai_analysis_results = []
        
    def collect_data(self, duration: int = None) -> List[Dict[str, Any]]:
        """收集光照数据"""
        if duration is None:
            duration = self.config.DEFAULT_DURATION
        
        collected_data = []
        start_time = time.time()
        sample_count = 0
        
        logger.info(f"开始收集数据，时长 {duration} 秒...")
        
        try:
            while time.time() - start_time < duration:
                # 读取传感器数据
                light_intensity = self.sensor.read_light_intensity()
                light_change = self.sensor.calculate_light_change(light_intensity)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                # 分析情感
                emotion_analysis = self.analyzer.analyze_light_data(light_intensity, light_change)
                
                # 创建数据点
                data_point = {
                    "timestamp": timestamp,
                    "light_intensity": light_intensity,
                    "light_change": round(light_change, 2),
                    "brightness": 255 - light_intensity,
                    "primary_emotion": emotion_analysis["primary_emotion"],
                    "emotion_keywords": emotion_analysis["emotion_keywords"],
                    "color_code": emotion_analysis["color_code"],
                    "emotional_intensity": emotion_analysis["emotional_intensity"],
                    "explanation": emotion_analysis["explanation"]
                }
                
                # 添加到缓冲区
                collected_data.append(data_point)
                self.data_buffer.append(data_point)
                
                # 触发AI分析的条件
                if light_change > self.config.LIGHT_THRESHOLD and len(self.data_buffer) >= self.config.BATCH_SIZE:
                    self._trigger_ai_analysis()
                
                # 保存数据的条件
                if len(collected_data) % self.config.SAVE_INTERVAL == 0:
                    self._save_data(collected_data)
                
                sample_count += 1
                logger.info(f"样本 {sample_count}: 光照强度={light_intensity}, 变化率={light_change:.2f}, 情绪={emotion_analysis['primary_emotion']}")
                
                time.sleep(self.config.SAMPLE_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("数据收集被用户中断")
        except Exception as e:
            logger.error(f"数据收集过程中出错: {e}")
        
        return collected_data
    
    def _trigger_ai_analysis(self):
        """触发AI分析"""
        try:
            logger.info("触发AI分析...")
            current_data = list(self.data_buffer)
            
            if len(current_data) >= self.config.BATCH_SIZE:
                ai_result = self.analyzer.analyze_with_ai(current_data)
                if ai_result["success"]:
                    ai_result["trigger_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ai_result["data_points_analyzed"] = len(current_data)
                    self.ai_analysis_results.append(ai_result)
                    logger.info("AI分析成功完成")
                    
                    # 打印AI分析结果
                    self._print_ai_analysis(ai_result)
                else:
                    logger.warning(f"AI分析失败: {ai_result.get('error', '未知错误')}")
                    
        except Exception as e:
            logger.error(f"触发AI分析时出错: {e}")
    
    def _print_ai_analysis(self, ai_result: Dict[str, Any]):
        """打印AI分析结果"""
        print("\n" + "="*100)
        print("AI 情感分析结果")
        print("="*100)
        print(f"\n分析时间: {ai_result.get('analysis_time', 'N/A')}")
        print(f"分析的数据点数量: {ai_result.get('data_points_analyzed', 0)}")
        
        print("\n" + "-"*100)
        print("MOONDREAM 分析 (视觉情感评估):")
        print("-"*100)
        print(ai_result.get('moondream_analysis', '无分析可用'))
        
        print("\n" + "-"*100)
        print("DEEPSEEK 分析 (心理评估):")
        print("-"*100)
        print(ai_result.get('deepseek_analysis', '无分析可用'))
        
        print("\n" + "-"*100)
        print("数据摘要:")
        print("-"*100)
        print(ai_result.get('data_summary', '无摘要可用'))
        print("\n" + "="*100)
    
    def _save_data(self, data: List[Dict[str, Any]]):
        """保存数据到Excel"""
        try:
            if not data:
                return
            
            # 转换为DataFrame
            df_new = pd.DataFrame(data)
            
            # 合并到主DataFrame
            if self.data_frame.empty:
                self.data_frame = df_new
            else:
                self.data_frame = pd.concat([self.data_frame, df_new], ignore_index=True)
            
            # 保存到Excel
            self.data_frame.to_excel(self.config.DATA_FILE, index=False)
            logger.info(f"数据已保存到 {self.config.DATA_FILE} ({len(self.data_frame)} 条记录)")
            
        except Exception as e:
            logger.error(f"保存数据时出错: {e}")
    
    def generate_chart(self):
        """生成光照变化图表"""
        if self.data_frame.empty:
            logger.warning("无可用数据生成图表")
            return
        
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            fig.suptitle('光照情感分析结果', fontsize=16, fontweight='bold')
            
            # 1. 光照强度随时间变化
            ax1 = axes[0, 0]
            ax1.plot(self.data_frame.index, self.data_frame['light_intensity'], 
                    'b-', linewidth=2, alpha=0.7, label='光照强度')
            ax1.set_xlabel('样本索引')
            ax1.set_ylabel('光照强度 (0-255)')
            ax1.set_title('光照强度随时间变化')
            ax1.grid(True, alpha=0.3)
            ax1.legend()
            
            # 2. 光照变化率
            ax2 = axes[0, 1]
            ax2.bar(self.data_frame.index, self.data_frame['light_change'], 
                   color='orange', alpha=0.7, label='变化率')
            ax2.set_xlabel('样本索引')
            ax2.set_ylabel('光照变化率')
            ax2.set_title('光照变化率')
            ax2.grid(True, alpha=0.3)
            ax2.legend()
            
            # 3. 情感分布
            ax3 = axes[1, 0]
            emotion_counts = self.data_frame['primary_emotion'].value_counts()
            colors = [self.analyzer._select_color(emotion) for emotion in emotion_counts.index]
            ax3.pie(emotion_counts.values, labels=emotion_counts.index, colors=colors,
                   autopct='%1.1f%%', startangle=90)
            ax3.set_title('情感分布')
            
            # 4. 情感颜色标签
            ax4 = axes[1, 1]
            ax4.set_title('情感颜色映射')
            ax4.axis('off')
            
            # 显示颜色标签
            unique_emotions = self.data_frame['primary_emotion'].unique()
            y_position = 0.9
            
            for emotion in unique_emotions:
                color = self.analyzer._select_color(emotion)
                count = (self.data_frame['primary_emotion'] == emotion).sum()
                
                # 创建颜色方块
                rect = patches.Rectangle((0.1, y_position-0.05), 0.1, 0.05, 
                                       facecolor=color, edgecolor='black', linewidth=1)
                ax4.add_patch(rect)
                
                # 添加文本
                ax4.text(0.25, y_position, f'{emotion} ({count})', 
                        fontsize=10, verticalalignment='center')
                y_position -= 0.1
            
            plt.tight_layout()
            plt.savefig(self.config.CHART_FILE, dpi=300, bbox_inches='tight')
            logger.info(f"图表已保存到 {self.config.CHART_FILE}")
            
            plt.show()
            
        except Exception as e:
            logger.error(f"生成图表时出错: {e}")
    
    def run_test_analysis(self, num_samples: int = 20):
        """运行测试分析"""
        print("\n" + "="*100)
        print("运行测试分析 (20个样本数据点)")
        print("="*100)
        
        # 生成测试数据
        test_data = []
        base_time = datetime.now()
        
        patterns = [
            ("gradual_increase", "逐渐增加"),
            ("gradual_decrease", "逐渐减少"),
            ("sudden_drop", "突然下降"),
            ("sudden_spike", "突然上升"),
            ("stable_dark", "稳定黑暗"),
            ("stable_bright", "稳定明亮"),
            ("fluctuating", "波动变化"),
            ("rapid_changes", "快速变化"),
            ("periodic", "周期性变化"),
            ("random", "随机变化")
        ]
        
        for i in range(num_samples):
            pattern_idx = i % len(patterns)
            pattern_type, pattern_desc = patterns[pattern_idx]
            
            # 根据模式生成测试数据
            if pattern_type == "gradual_increase":
                light_intensity = int(50 + (i * 10) % 205)
                light_change = 5.0 + (i * 0.5)
            elif pattern_type == "gradual_decrease":
                light_intensity = int(200 - (i * 8) % 180)
                light_change = 8.0 - (i * 0.4)
            elif pattern_type == "sudden_drop":
                light_intensity = 220 if i % 4 == 0 else 80
                light_change = 60.0 + np.random.random() * 40
            elif pattern_type == "sudden_spike":
                light_intensity = 30 if i % 5 == 0 else 180
                light_change = 50.0 + np.random.random() * 30
            elif pattern_type == "stable_dark":
                light_intensity = 200 + int(np.random.random() * 40)
                light_change = 2.0 + np.random.random() * 3
            elif pattern_type == "stable_bright":
                light_intensity = 30 + int(np.random.random() * 40)
                light_change = 1.5 + np.random.random() * 2
            elif pattern_type == "fluctuating":
                base = 100
                fluctuation = 50 * np.sin(i * 0.5)
                light_intensity = int(base + fluctuation)
                light_intensity = max(0, min(255, light_intensity))
                light_change = 20.0 + np.random.random() * 20
            elif pattern_type == "rapid_changes":
                light_intensity = int(np.random.random() * 255)
                light_change = 80.0 + np.random.random() * 70
            elif pattern_type == "periodic":
                period = 4
                light_intensity = int(100 + 80 * np.sin(2 * np.pi * i / period))
                light_intensity = max(0, min(255, light_intensity))
                light_change = 30.0 + 20 * abs(np.cos(2 * np.pi * i / period))
            else:
                light_intensity = int(np.random.random() * 255)
                light_change = np.random.random() * 100
            
            light_intensity = max(0, min(255, light_intensity))
            light_change = max(0, min(150, light_change))
            
            timestamp = (base_time + timedelta(minutes=i*5)).strftime("%Y-%m-%d %H:%M:%S")
            
            # 分析情感
            emotion_analysis = self.analyzer.analyze_light_data(light_intensity, light_change)
            
            data_point = {
                "id": i + 1,
                "timestamp": timestamp,
                "pattern_type": pattern_type,
                "pattern_description": pattern_desc,
                "light_intensity": light_intensity,
                "light_change": round(light_change, 2),
                "brightness": 255 - light_intensity,
                "primary_emotion": emotion_analysis["primary_emotion"],
                "emotion_keywords": emotion_analysis["emotion_keywords"],
                "color_code": emotion_analysis["color_code"],
                "emotional_intensity": emotion_analysis["emotional_intensity"],
                "explanation": emotion_analysis["explanation"]
            }
            
            test_data.append(data_point)
        
        # 保存测试数据
        test_df = pd.DataFrame(test_data)
        test_file = "light_emotion_test_data.xlsx"
        test_df.to_excel(test_file, index=False)
        print(f"\n测试数据已保存到: {test_file}")
        
        # 显示测试结果
        self._display_test_results(test_data)
        
        # 触发AI分析
        if len(test_data) >= self.config.BATCH_SIZE:
            ai_result = self.analyzer.analyze_with_ai(test_data)
            if ai_result["success"]:
                self._print_ai_analysis(ai_result)
        
        return test_data
    
    def _display_test_results(self, test_data: List[Dict[str, Any]]):
        """显示测试结果"""
        print("\n" + "="*100)
        print("测试数据分析结果")
        print("="*100)
        print(f"{'ID':<4} {'时间戳':<20} {'模式':<15} {'强度':<10} {'变化':<8} {'情绪':<15} {'颜色':<10}")
        print("-"*100)
        
        for data in test_data:
            print(f"{data['id']:<4} {data['timestamp']:<20} {data['pattern_description']:<15} "
                  f"{data['light_intensity']:<10} {data['light_change']:<8.2f} "
                  f"{data['primary_emotion']:<15} {data['color_code']:<10}")
        
        # 统计信息
        intensities = [d['light_intensity'] for d in test_data]
        changes = [d['light_change'] for d in test_data]
        emotions = [d['primary_emotion'] for d in test_data]
        
        print("\n" + "="*100)
        print("统计信息")
        print("="*100)
        print(f"总数据点: {len(test_data)}")
        print(f"平均光照强度: {np.mean(intensities):.2f}")
        print(f"平均变化率: {np.mean(changes):.2f}")
        print(f"最亮时刻: {min(intensities)}")
        print(f"最暗时刻: {max(intensities)}")
        
        emotion_counts = {}
        for emotion in emotions:
            emotion_counts[emotion] = emotion_counts.get(emotion, 0) + 1
        
        print("\n情绪分布:")
        for emotion, count in emotion_counts.items():
            percentage = (count / len(test_data)) * 100
            print(f"  {emotion}: {count} ({percentage:.1f}%)")
    
    def cleanup(self):
        """清理资源"""
        self.running = False
        self.sensor.close()
        logger.info("系统清理完成")

# ============================================================================
# 主函数
# ============================================================================
def main():
    """主函数"""
    print("\n" + "="*100)
    print("智能光照情感分析系统")
    print("="*100)
    print("功能：")
    print("1. 实时监测环境光照强度")
    print("2. 分析光照变化对应的情感")
    print("3. 使用AI模型进行深度情感分析")
    print("4. 生成数据图表和报告")
    print("="*100)
    
    # 创建系统实例
    config = SystemConfig()
    system = IntelligentLightEmotionSystem(config)
    
    try:
        # 选项菜单
        while True:
            print("\n" + "="*50)
            print("主菜单")
            print("="*50)
            print("1. 运行实时数据收集 (5分钟)")
            print("2. 运行测试分析 (20个样本)")
            print("3. 生成图表")
            print("4. 显示AI分析结果")
            print("5. 退出")
            print("="*50)
            
            choice = input("请选择操作 (1-5): ").strip()
            
            if choice == "1":
                # 运行实时数据收集
                duration = input("输入收集时长(秒，默认300): ").strip()
                duration = int(duration) if duration else 300
                
                data = system.collect_data(duration)
                print(f"\n数据收集完成，共收集 {len(data)} 个数据点")
                system._save_data(data)
                
            elif choice == "2":
                # 运行测试分析
                test_data = system.run_test_analysis(20)
                
            elif choice == "3":
                # 生成图表
                system.generate_chart()
                
            elif choice == "4":
                # 显示AI分析结果
                if system.ai_analysis_results:
                    for i, result in enumerate(system.ai_analysis_results, 1):
                        print(f"\nAI分析结果 #{i}:")
                        system._print_ai_analysis(result)
                else:
                    print("暂无AI分析结果")
                    
            elif choice == "5":
                # 退出
                print("正在退出系统...")
                break
                
            else:
                print("无效选择，请重新输入")
                
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {e}")
        traceback.print_exc()
    finally:
        system.cleanup()
        print("\n系统已关闭")

if __name__ == "__main__":
    main()