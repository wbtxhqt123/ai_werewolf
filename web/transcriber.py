import logging
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioTranscriber:
    """Handles audio transcription using a pre-trained speech recognition model.

    This class uses the Hugging Face `transformers` library to load a model from the
    `openai/whisper-tiny` checkpoint. It automatically selects the best available
    device (CUDA, MPS, or CPU) for inference.
    """
    def __init__(self, model_name="openai/whisper-tiny"):
        """Initializes the transcription pipeline.

        Args:
            model_name: The name of the Hugging Face model to use for transcription.
        """
        try:
            import torch
            from transformers import pipeline
        except ImportError as e:
            logger.error("torch or transformers not installed. Install via requirements-audio.txt.")
            raise RuntimeError(
                "Audio transcription requires 'torch' and 'transformers'. "
                "Please install them via: pip install -r requirements-audio.txt"
            ) from e

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            self.device = "mps"
            
        logger.info(f"Initializing AudioTranscriber with model {model_name} on {self.device}")
        
        try:
            self.pipe = pipeline(
                "automatic-speech-recognition",
                model=model_name,
                device=self.device
            )
        except Exception as e:
            logger.error(f"Failed to initialize pipeline: {e}")
            raise e

    def transcribe(self, audio_input, language: str | None = None) -> str:
        """Converts speech from an audio input into text.

        Args:
            audio_input: The path to the audio file to be transcribed.
            language: An optional language code (e.g., 'en', 'zh') to guide the
                transcription. If provided, it forces the model to transcribe in that
                language.

        Returns:
            The transcribed text as a string, or an empty string if an error occurs.
        """
        try:
            generate_kwargs = {}
            if language:
                generate_kwargs["language"] = language
                generate_kwargs["task"] = "transcribe"

            result = self.pipe(audio_input, generate_kwargs=generate_kwargs)
            text = result["text"]
            logger.info(f"Transcription result: {text}")
            return text
        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            return ""

# Singleton instance for easy import
_transcriber = None

def get_transcriber():
    """Returns a singleton instance of the `AudioTranscriber`.

    This function ensures that the transcription model is only loaded into memory
    once, improving performance and reducing resource consumption.
    """
    global _transcriber
    if _transcriber is None:
        _transcriber = AudioTranscriber()
    return _transcriber
