"""
Subtitle processing utilities for SEMAMORPH.
Handles SRT file parsing and subtitle-to-plot conversion.
"""

import re
import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path

from ..utils.logger_utils import setup_logging
from ..ai_models.ai_models import AzureChatOpenAI
from langchain_core.messages import HumanMessage
from ..utils.llm_utils import clean_llm_json_response
from ..utils.subtitle_utils import parse_srt_time_to_seconds, SubtitleEntry

logger = setup_logging(__name__)

@dataclass
class PlotScene:
    """Represents a plot scene with content and timing."""
    scene_number: int
    plot_segment: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    start_seconds: Optional[float] = None
    end_seconds: Optional[float] = None
    start_subtitle_index: Optional[int] = None  # Index of first subtitle in scene
    end_subtitle_index: Optional[int] = None    # Index of last subtitle in scene

def seconds_to_srt_time(seconds: float) -> str:
    """Convert seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}".replace('.', ',')

def format_subtitles_for_llm(subtitles: List[SubtitleEntry]) -> str:
    """Format subtitles for LLM processing."""
    formatted_lines = []
    for sub in subtitles:
        # Clean text of formatting tags
        clean_text = re.sub(r'<[^>]+>', '', sub.text)
        clean_text = re.sub(r'\{[^}]+\}', '', clean_text)
        clean_text = clean_text.strip()
        
        if clean_text:
            formatted_lines.append(f"[{sub.start_time} --> {sub.end_time}] {clean_text}")
    
    return '\n'.join(formatted_lines)

def generate_plot_from_subtitles(subtitles: List[SubtitleEntry], llm: AzureChatOpenAI, previous_season_summary: Optional[str] = None) -> Dict:
    """Generate detailed plot from subtitles using LLM with optional season context."""
    logger.info("Generating detailed plot from subtitles")
    
    # Format subtitles for LLM
    subtitle_text = format_subtitles_for_llm(subtitles)
    
    # Base prompt for plot generation
    base_prompt = """You are a script analyst that understands character names, relationships, and storylines from subtitles. You are also trained in ambiguity handling and know how to recognize when attribution is uncertain. 

Your task is to convert the provided subtitles into a detailed, scene-based plot summary in JSON. Be conservative in speaker attribution — never rely on stereotypes, character tropes, or assumed patterns.

**CRITICAL SPEAKER IDENTIFICATION RULES:**
- Only use specific names when the speaker is clear from the dialogue or the context and you feel confident.
- If the speaker is not clear in the text, use generic references like "a character", "someone", or "a voice".
- Do not assign actions based on behavior typical of a character.

**Bias Avoidance Principles:**
- Do not infer character behavior based on prior knowledge, stereotypes, or training corpus frequency.
- Do not assume that humiliating, comic, or dramatic actions belong to characters who often fill those roles unless **clearly** stated in the text.
- When multiple characters are present and the speaker isn't identified, use:  
  - "one of the group of footballers"  
  - "a male character"  
  - "an unidentified person"  
  as needed.

**If unsure, you MUST default to generic labeling** — uncertainty is better than incorrect confidence.
**Output Format (JSON only):**
[
  {{
    "scene_number": 1,
    "plot_segment": "..."
  }},
  {{
    "scene_number": 2,
    "plot_segment": "..."
  }}
]

**Plot Segment Requirements:**
- Extract every narrative event from the subtitles in chronological order
- Use clear, concise sentences (no run-on sentences)
- Include all dialogue, actions, and story developments
- Maintain objective tone - report what happens, don't interpret
- Number scenes based on natural story breaks or setting changes
- Correctly separate scenes, trying to not make big large sequences of scenes but rather smaller and focused scenes.
- Make the plot segment detailed and specific, indicating also the character present in the scene.

REMEMBER ALWAYS: Don't be overly confident, if you are not certain about the speaker, use generic references. 

"""

    # Add season context if available
    if previous_season_summary:
        context_prompt = f"""
                                **Previous Season Context:**
                                Use the following summary of previous episodes to better understand character relationships, ongoing storylines, and narrative context. This context helps you interpret the subtitles more accurately but should NOT be included in your plot output - only use it for understanding.

                                {previous_season_summary}

                                **Important:** Your plot output should ONLY describe what happens in the current episode subtitles. The context is provided to help you better understand character names, relationships, and ongoing storylines when interpreting the subtitles.
                                """
        
        full_prompt = f"{base_prompt}\n{context_prompt}"
        
        logger.info("Using previous season context for plot generation")
    else:
        full_prompt = base_prompt
    
    full_prompt += f"\n\nSubtitles:\n{subtitle_text}"
    
    logger.info(f"Sending plot generation request to LLM (subtitle length: {len(subtitle_text)} chars)")
    logger.info(f"Prompt total length: {len(full_prompt)} chars")
    logger.info(f"Using LLM type: {type(llm).__name__}")
    logger.debug(f"Full prompt preview (first 500 chars): {full_prompt[:500]}...")
    logger.debug(f"LLM configuration: {getattr(llm, 'model_name', 'Unknown')} | Temperature: {getattr(llm, 'temperature', 'Unknown')}")
    
    try:
        logger.info("🔄 Invoking LLM for plot generation...")
        
        # Add timing information
        import time
        start_time = time.time()
        
        response = llm.invoke([HumanMessage(content=full_prompt)])
        
        end_time = time.time()
        elapsed = end_time - start_time
        logger.info(f"✅ LLM response received successfully in {elapsed:.2f} seconds")
        logger.debug(f"Response preview (first 200 chars): {response.content[:200]}...")
    except Exception as e:
        logger.error(f"❌ LLM invocation failed: {e}")
        logger.error(f"LLM type: {type(llm)}")
        logger.error(f"Prompt length: {len(full_prompt)}")
        raise
    
    try:
        # Clean and parse JSON response
        plot_data = clean_llm_json_response(response.content)
        
        if isinstance(plot_data, list):
            # Convert list format to scenes dict
            scenes_dict = {"scenes": plot_data}
        elif isinstance(plot_data, dict) and "scenes" in plot_data:
            scenes_dict = plot_data
        else:
            # Assume the dict itself contains scenes
            scenes_dict = {"scenes": list(plot_data.values()) if isinstance(plot_data, dict) else plot_data}
        
        logger.info(f"Generated plot with {len(scenes_dict.get('scenes', []))} scenes")
        return scenes_dict
        
    except Exception as e:
        logger.error(f"Error parsing LLM response for plot generation: {e}")
        logger.error(f"Raw response: {response.content[:500]}...")
        raise

def save_plot_files(plot_data: Dict, output_dir: str, episode_prefix: str) -> Tuple[str, str]:
    """Save plot data as both TXT and JSON files."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Extract scenes from the data structure
    scenes = plot_data.get("scenes", [])
    
    # Generate text format
    txt_content = []
    for scene in scenes:
        scene_number = scene.get("scene_number", "Unknown")
        plot_segment = scene.get("plot_segment", "")
        txt_content.append(f"Scene {scene_number}: {plot_segment}")
    
    # Save TXT file
    txt_path = output_path / f"{episode_prefix}_plot.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(txt_content))
    
    # Save JSON file
    json_path = output_path / f"{episode_prefix}_plot.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(plot_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved plot files: {txt_path} and {json_path}")
    return str(txt_path), str(json_path)

def save_scene_timestamps(scenes: List[PlotScene], output_dir: str, episode_prefix: str) -> str:
    """Save scene timestamp mappings to JSON file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timestamp_data = {
        "scenes": [
            {
                "scene_number": scene.scene_number,
                "plot_segment": scene.plot_segment,
                "start_time": scene.start_time,
                "end_time": scene.end_time,
                "start_seconds": scene.start_seconds,
                "end_seconds": scene.end_seconds,
                "start_subtitle_index": scene.start_subtitle_index,
                "end_subtitle_index": scene.end_subtitle_index
            }
            for scene in scenes
        ]
    }
    
    json_path = output_path / f"{episode_prefix}_scene_timestamps.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(timestamp_data, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Saved scene timestamps: {json_path}")
    return str(json_path)

def load_previous_season_summary(season_summary_path: str) -> Optional[str]:
    """
    Load the previous season summary if it exists.
    
    Args:
        season_summary_path (str): Path to the season summary file
        
    Returns:
        Optional[str]: The season summary content, or None if not found
    """
    try:
        if Path(season_summary_path).exists():
            from backend.src.utils.text_utils import load_text
            summary = load_text(season_summary_path)
            if summary.strip():
                logger.info(f"Loaded previous season summary from: {season_summary_path}")
                return summary
        
        logger.info("No previous season summary found")
        return None
        
    except Exception as e:
        logger.error(f"Error loading previous season summary: {e}")
        return None

# ================================
# NEW SIMPLIFIED SCENE BOUNDARY DETECTION
# ================================

# Import the new simplified approach
from .scene_boundary_detection import map_scenes_to_timestamps_simple

def map_scenes_to_timestamps(
    scenes: List[PlotScene], 
    subtitles: List[SubtitleEntry], 
    llm: AzureChatOpenAI,
    correction_strategy: str = "intelligent"
) -> List[PlotScene]:
    """
    Map scenes to timestamps using the new simplified boundary detection approach.
    
    This function uses LLM to identify subtitle boundaries between scenes,
    then extracts timestamps mechanically from the SRT data.
    
    Args:
        scenes: List of scenes to map
        subtitles: List of subtitle entries
        llm: LLM for boundary detection
        correction_strategy: Kept for compatibility, but not used in new approach
        
    Returns:
        List of scenes with timestamps
    """
    logger.info("🆕 Using new simplified scene boundary detection approach")
    return map_scenes_to_timestamps_simple(scenes, subtitles, llm)
