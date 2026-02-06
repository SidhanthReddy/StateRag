from typing import Optional
import os
import time
from dotenv import load_dotenv


class LLMAdapter:
    """
    Minimal LLM transport layer with proper rate limiting and retry logic.
    Stateless. No parsing. No validation.
    """

    def __init__(self, provider: str = "mock"):
        """
        provider:
          - "mock"
          - "openai"
          - "gemini"
        """
        self.provider = provider.lower()

        # Load .env if present
        load_dotenv()

        if self.provider == "openai":
            self._init_openai()

        elif self.provider == "gemini":
            self._init_gemini()

        elif self.provider == "mock":
            pass

        else:
            raise ValueError(f"Unknown LLM provider: {provider}")

    # --------------------------------------------------
    # Public API
    # --------------------------------------------------

    def generate(self, prompt: str) -> str:
        """
        Sends prompt to LLM and returns raw text output.
        Includes retry logic for rate limits.
        """
        if self.provider == "mock":
            return self._mock_response(prompt)

        if self.provider == "openai":
            return self._openai_response(prompt)

        if self.provider == "gemini":
            return self._gemini_response_with_retry(prompt)

        raise RuntimeError("Invalid LLM provider state")

    # --------------------------------------------------
    # Provider initializers
    # --------------------------------------------------

    def _init_openai(self):
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("Run: pip install openai")

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set")

        self.openai_client = OpenAI(api_key=api_key)

    def _init_gemini(self):
        try:
            import google.generativeai as genai
        except ImportError:
            raise RuntimeError("Run: pip install google-generativeai")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        genai.configure(api_key=api_key)
        self.genai = genai
        
        # Use gemini-2.5-flash - the newest and best free tier model
        # Available models from your API (that support generateContent):
        # - gemini-2.5-flash (BEST - newest, fast, good quality)
        # - gemini-2.5-pro (premium quality but slower)
        # - gemini-2.0-flash (older version)
        # - gemini-flash-latest (alias to latest flash)
        # - gemini-pro-latest (alias to latest pro)
        
        self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")
        print(f"✅ Using Gemini model: gemini-2.5-flash")

    # --------------------------------------------------
    # Providers
    # --------------------------------------------------

    def _mock_response(self, prompt: str) -> str:
        return (
            "FILE: components/Navbar.tsx\n"
            "import React from 'react';\n\n"
            "export default function Navbar() {\n"
            "  return (\n"
            "    <nav className='sticky top-0 z-50 bg-white shadow-md'>\n"
            "      <div className='container mx-auto px-4 py-3 flex items-center justify-between'>\n"
            "        <div className='font-bold text-xl'>Logo</div>\n"
            "        <div className='flex gap-4'>\n"
            "          <a href='#home'>Home</a>\n"
            "          <a href='#about'>About</a>\n"
            "        </div>\n"
            "      </div>\n"
            "    </nav>\n"
            "  );\n"
            "}\n"
        )

    def _openai_response(self, prompt: str) -> str:
        """OpenAI with updated API (v1.0+)"""
        response = self.openai_client.chat.completions.create(
            model="gpt-4o-mini",  # Cheaper, faster model
            messages=[
                {"role": "system", "content": "You are a stateless code generator."},
                {"role": "user", "content": prompt},
            ],
            temperature=0,
        )
        return response.choices[0].message.content

    def _gemini_response_with_retry(self, prompt: str, max_retries: int = 3) -> str:
        """
        Gemini with exponential backoff retry logic for rate limits
        
        Gemini Free Tier Limits:
        - 15 requests per minute (RPM)
        - 1 million tokens per minute (TPM)
        - 1,500 requests per day (RPD)
        """
        
        for attempt in range(max_retries):
            try:
                response = self.gemini_model.generate_content(
                    prompt,
                    generation_config={
                        "temperature": 0,
                        "max_output_tokens": 2048,  # Reduced from 4096 to save quota
                    },
                )
                return response.text
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error (429)
                if "429" in error_str or "Resource exhausted" in error_str or "quota" in error_str.lower():
                    if attempt < max_retries - 1:
                        # Exponential backoff: wait 5s, 15s, 45s
                        wait_time = 5 * (3 ** attempt)
                        print(f"⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise RuntimeError(
                            f"Gemini API rate limit exceeded after {max_retries} retries. "
                            f"Free tier limits: 15 requests/minute, 1500 requests/day. "
                            f"Please wait a few minutes and try again."
                        )
                
                # Check for 404 model not found
                elif "404" in error_str or "not found" in error_str.lower():
                    raise RuntimeError(
                        f"Gemini model error: {error_str}\n"
                        f"The model might not be available with your API key. "
                        f"Try running: python list_models.py"
                    )
                
                # Other errors - re-raise immediately
                else:
                    raise RuntimeError(f"Gemini API error: {error_str}")
        
        raise RuntimeError("Max retries exceeded")