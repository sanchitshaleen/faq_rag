import json
import os
from typing import Optional, Dict, Any

class FAQDatabase:
    """JSON file store representing rich FAQ metadata."""

    def __init__(self, db_path: str = "faq_metadata.json"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Create the JSON file if it doesn't exist."""
        if not os.path.exists(self.db_path):
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump({}, f)

    def _load_data(self) -> Dict[str, dict]:
        """Load data from the JSON file."""
        if not os.path.exists(self.db_path):
            return {}
        with open(self.db_path, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}

    def _save_data(self, data: Dict[str, dict]):
        """Save data to the JSON file."""
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def insert_qa(self, faqs: list[Dict[str, Any]]):
        """Insert multiple Q-A records into the JSON file."""
        data = self._load_data()
        for f in faqs:
            # We enforce saving all fields as they were passed in
            faq_id = f.get("faq_id")
            if faq_id:
                data[faq_id] = f
        self._save_data(data)

    def get_qa(self, faq_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single QA record by ID."""
        data = self._load_data()
        return data.get(faq_id)

    def delete_all(self):
        """Clear all records from the JSON file."""
        self._save_data({})

    def count(self) -> int:
        """Count total records in the JSON file."""
        data = self._load_data()
        return len(data)

if __name__ == "__main__":
    db = FAQDatabase()
    print(f"Database initialized at {os.path.abspath(db.db_path)}")
    print(f"Total records: {db.count()}")
