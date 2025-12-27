# ai_reply.py

import os
from typing import Tuple

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

load_dotenv()


class ReplySuggester:
    """
    Generates two reply suggestions for a given email content.
    """

    def __init__(self):
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.llm = ChatOpenAI(model=model, temperature=0.3)

        self.prompt = PromptTemplate(
            input_variables=["email_text", "tone"],
            template=(
                "You are a helpful assistant that writes email replies.\n\n"
                "Write a {tone} reply to the email below.\n"
                "Rules:\n"
                "- Be concise (4-8 sentences)\n"
                "- Sound natural and professional\n"
                "- Do NOT invent facts; if something is missing, ask a short clarifying question\n\n"
                "EMAIL:\n"
                "{email_text}\n\n"
                "REPLY:\n"
            ),
        )

    def suggest_two(self, email_text: str) -> Tuple[str, str]:
        """
        Returns:
          suggestion_1: neutral/professional
          suggestion_2: slightly warmer/friendlier
        """
        s1 = (self.prompt | self.llm).invoke({"email_text": email_text, "tone": "professional and direct"}).content
        s2 = (self.prompt | self.llm).invoke({"email_text": email_text, "tone": "professional but warm"}).content
        return s1.strip(), s2.strip()