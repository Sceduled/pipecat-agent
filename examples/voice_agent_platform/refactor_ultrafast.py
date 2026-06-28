import os

file_path = r"c:\apps\pipecat-main\examples\real_estate_agent\ultrafast_outbound_agent.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace variables and functions
content = content.replace("pending_multilingual_sessions", "pending_ultrafast_sessions")
content = content.replace("run_multilingual_outbound", "run_ultrafast_outbound")

# Replace OpenAILLMService signature
content = content.replace(
    "openai_api_key: str,",
    "groq_api_key: str,"
)

# Replace the actual LLM instance
old_llm = """    # --- LLM ---
    llm = OpenAILLMService(
        api_key=openai_api_key,
        settings=OpenAILLMService.Settings(
            model="gpt-4o-mini",
            system_instruction=system_prompt_final,
        ),
    )"""

new_llm = """    # --- LLM ---
    llm = OpenAILLMService(
        api_key=groq_api_key,
        base_url="https://api.groq.com/openai/v1",
        settings=OpenAILLMService.Settings(
            model="llama-3.3-70b-versatile",
            system_instruction=system_prompt_final,
        ),
    )"""
content = content.replace(old_llm, new_llm)

# Replace VAD
old_vad = """            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(min_volume=0.1, confidence=0.5, stop_secs=0.5)
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.4)],
            ),"""

new_vad = """            vad_analyzer=SileroVADAnalyzer(
                params=VADParams(min_volume=0.1, confidence=0.5, stop_secs=0.3)
            ),
            user_turn_strategies=UserTurnStrategies(
                stop=[SpeechTimeoutUserTurnStopStrategy(user_speech_timeout=0.3)],
            ),"""
content = content.replace(old_vad, new_vad)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Refactored ultrafast_outbound_agent.py")
