from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Garantir que etl/ está no sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "etl"))

from notify_telegram import format_message, get_credentials, load_env_file, notify_telegram


class TestNotifyTelegram(unittest.TestCase):
    def test_format_message_sucesso(self):
        msg = format_message(projeto="ANAC", status="sucesso", duracao="5 min", detalhes="140k voos")
        self.assertIn("[ANAC] Ingestão Concluída", msg)
        self.assertIn("✅", msg)
        self.assertIn("5 min", msg)
        self.assertIn("140k voos", msg)

    def test_format_message_falha_escapes_html(self):
        msg = format_message(projeto="ANAC", status="falha", erros="<script>alert('xss')</script> & syntax error")
        self.assertIn("[ANAC] Falha na Ingestão", msg)
        self.assertIn("🚨", msg)
        self.assertIn("&lt;script&gt;", msg)
        self.assertIn("&amp;", msg)

    def test_load_env_file(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
            f.write("TELEGRAM_BOT_TOKEN=token_test_123\n")
            f.write("TELEGRAM_CHAT_ID=chat_test_456\n")
            f.write("# comentario\n")
            f.write("IGNORED_LINE\n")
            temp_path = Path(f.name)

        saved_token = os.environ.pop("TELEGRAM_BOT_TOKEN", None)
        saved_chat = os.environ.pop("TELEGRAM_CHAT_ID", None)
        try:
            load_env_file(temp_path)
            self.assertEqual(os.environ.get("TELEGRAM_BOT_TOKEN"), "token_test_123")
            self.assertEqual(os.environ.get("TELEGRAM_CHAT_ID"), "chat_test_456")
        finally:
            temp_path.unlink(missing_ok=True)
            if saved_token is not None:
                os.environ["TELEGRAM_BOT_TOKEN"] = saved_token
            else:
                os.environ.pop("TELEGRAM_BOT_TOKEN", None)
            if saved_chat is not None:
                os.environ["TELEGRAM_CHAT_ID"] = saved_chat
            else:
                os.environ.pop("TELEGRAM_CHAT_ID", None)

    def test_notify_telegram_sem_credenciais_retorna_true(self):
        with patch.dict(os.environ, {}, clear=True), \
             patch("notify_telegram.get_credentials", return_value=("", "")):
            res = notify_telegram(projeto="ANAC", status="sucesso")
            self.assertTrue(res)

    @patch("urllib.request.urlopen")
    def test_notify_telegram_envio_com_sucesso(self, mock_urlopen):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        with patch("notify_telegram.get_credentials", return_value=("mock_tok", "12345")):
            res = notify_telegram(
                projeto="ANAC",
                status="sucesso",
                duracao="2 min",
                detalhes="OK",
            )
            self.assertTrue(res)
            self.assertEqual(mock_urlopen.call_count, 1)

    @patch("urllib.request.urlopen")
    def test_notify_telegram_trata_excecao_de_rede(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("Network unreachable")

        with patch("notify_telegram.get_credentials", return_value=("mock_tok", "12345")):
            res = notify_telegram(projeto="ANAC", status="falha", erros="erro mock")
            self.assertFalse(res)


if __name__ == "__main__":
    unittest.main()
