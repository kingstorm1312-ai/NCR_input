
import sys
import os
import unittest
from unittest.mock import MagicMock

# Mock streamlit before importing pages
sys.modules["streamlit"] = MagicMock()
sys.modules["streamlit.components.v1"] = MagicMock()

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestPhase1(unittest.TestCase):
    def test_imports(self):
        """Test that all key modules import without error."""
        try:
            import core.auth
            import core.master_data
            import core.gsheets
            # We can't easily import pages because they run code on import involved with st.sidebar etc.
            # But importing core ensures the foundation is solid.
            print("✅ Core modules imported successfully.")
        except ImportError as e:
            self.fail(f"Import failed: {e}")

    def test_gsheets_batch_logic(self):
        """Test the logic of smart_append_batch without actual API call."""
        from core.gsheets import smart_append_batch
        
        mock_ws = MagicMock()
        mock_ws.row_values.return_value = ["col1", "col2"]
        
        data = [{"col1": "A", "col2": "B"}, {"col1": "C", "col2": "D"}]
        
        # Test
        count = smart_append_batch(mock_ws, data)
        
        # Verify
        self.assertEqual(count, 2)
        mock_ws.append_rows.assert_called_once()
        args = mock_ws.append_rows.call_args[0][0]
        self.assertEqual(args, [["A", "B"], ["C", "D"]])
        print("✅ Batch append logic verified.")

if __name__ == '__main__':
    unittest.main()
