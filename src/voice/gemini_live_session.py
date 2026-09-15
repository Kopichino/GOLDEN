"""Gemini Live adapter for the GOLDEN family-history conversation."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from src.config import settings
from src.voice.family_voice_session import FAMILY_AGENT_SYSTEM_PROMPT, FamilyVoiceSession


class GeminiLiveFamilySession:
    """Create a constrained Gemini Live session for one family call."""

    def __init__(self, model: str | None = None) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_LIVE_MODEL

    @staticmethod
    def build_tools() -> list[Any]:
        """Return only the tool declarations needed for family history."""
        from google.genai import types

        def declaration(name: str, description: str, value_type: str = "STRING") -> Any:
            value_schema = types.Schema(
                type=getattr(types.Type, value_type),
                description="Family-reported value",
            )
            if value_type == "ARRAY":
                value_schema.items = types.Schema(type=types.Type.STRING)
            return types.FunctionDeclaration(
                name=name,
                description=description,
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "value": value_schema,
                    },
                    required=["value"],
                ),
            )

        return [types.Tool(function_declarations=[
            types.FunctionDeclaration(
                name="record_consent",
                description="Record whether the family member explicitly consents to sharing history.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "consent_granted": types.Schema(type=types.Type.BOOLEAN),
                    },
                    required=["consent_granted"],
                ),
            ),
            declaration("record_allergies", "Record reported allergies as a list.", "ARRAY"),
            declaration("record_medications", "Record reported current medications as a list.", "ARRAY"),
            declaration("record_blood_group", "Record the reported blood group."),
            declaration("record_conditions", "Record reported pre-existing conditions as a list.", "ARRAY"),
            declaration("record_family_summary", "Record a concise family-reported summary."),
        ])]

    @asynccontextmanager
    async def connect(self) -> AsyncIterator[Any]:
        """Open a Gemini Live session and send the deterministic call trigger."""
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is required for live voice sessions")
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=self.api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=FAMILY_AGENT_SYSTEM_PROMPT,
            tools=self.build_tools(),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    prefix_padding_ms=200,
                    silence_duration_ms=500,
                ),
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=settings.GEMINI_VOICE_NAME,
                    ),
                ),
            ),
        )
        async with client.aio.live.connect(model=self.model, config=config) as session:
            await session.send_client_content(
                turns=[types.Content(role="user", parts=[types.Part.from_text(text="CALL_START")])],
                turn_complete=True,
            )
            yield session

    async def handle_tool_response(
        self,
        response: Any,
        live_session: Any,
        family_session: FamilyVoiceSession,
    ) -> None:
        """Apply Gemini function calls and return their results to Gemini."""
        tool_call = getattr(response, "tool_call", None)
        if not tool_call:
            return
        from google.genai import types

        function_responses = []
        for function_call in tool_call.function_calls:
            result = family_session.handle_tool_call(
                function_call.name,
                dict(function_call.args or {}),
            )
            function_responses.append(types.FunctionResponse(
                name=function_call.name,
                id=function_call.id,
                response=result,
            ))
        await live_session.send_tool_response(function_responses=function_responses)