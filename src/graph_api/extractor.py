from typing import List, Dict, Any
from gliner import GLiNER
import logging

logger = logging.getLogger(__name__)

class EntityExtractor:
    def __init__(self, model_name: str = "urchade/gliner_medium-v2.1"):
        """
        Initialize GLiNER model.
        Args:
            model_name: Name of the GLiNER model to use.
                        "urchade/gliner_medium-v2.1" is a good balance of speed and performance.
        """
        try:
            self.model = GLiNER.from_pretrained(model_name)
            self.labels = ["Disease", "Symptom", "Drug", "Treatment", "Anatomy", "Test"]
        except Exception as e:
            logger.error(f"Failed to load GLiNER model: {e}")
            self.model = None

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text.
        Args:
            text: Input text.
        Returns:
            List of dictionaries with 'text', 'label', 'score'.
        """
        if not self.model:
            return []
        
        try:
            entities = self.model.predict_entities(text, self.labels, threshold=0.5)
            # Format: [{'text': 'lung cancer', 'label': 'Disease', 'score': 0.98}, ...]
            return entities
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
