import os
from unittest.mock import MagicMock, patch

import pytest


class TestMaskApiKey:
    def test_api_key_masked(self):
        from backend.app.services.http_logging import _mask_api_key

        body = {"api_key": "sk-secret-12345", "model": "gpt-4o"}
        masked = _mask_api_key(body)
        assert masked["api_key"] == "***"
        assert masked["model"] == "gpt-4o"

    def test_no_api_key(self):
        from backend.app.services.http_logging import _mask_api_key

        body = {"model": "gpt-4o", "messages": []}
        masked = _mask_api_key(body)
        assert masked == body

    def test_none_body(self):
        from backend.app.services.http_logging import _mask_api_key

        assert _mask_api_key(None) is None
        assert _mask_api_key({}) == {}


class TestTruncateTextResponse:
    def test_truncate_long_content(self):
        from backend.app.services.http_logging import _truncate_text_response

        long_content = "x" * 3000
        resp = {
            "choices": [{"message": {"content": long_content}}],
            "usage": {"total_tokens": 100},
        }
        truncated = _truncate_text_response(resp)
        content = truncated["choices"][0]["message"]["content"]
        assert "[truncated" in content
        assert len(content) < 3000
        assert truncated["usage"] == {"total_tokens": 100}

    def test_short_content_unchanged(self):
        from backend.app.services.http_logging import _truncate_text_response

        short = "hello world"
        resp = {"choices": [{"message": {"content": short}}]}
        truncated = _truncate_text_response(resp)
        assert truncated["choices"][0]["message"]["content"] == short

    def test_image_response_unchanged(self):
        from backend.app.services.http_logging import _truncate_text_response

        resp = {"data": [{"url": "http://img.example.com/1.jpg"}]}
        truncated = _truncate_text_response(resp)
        assert truncated == resp


class TestAiHttpLogSuccess:
    def test_text_request_logged(self):
        from backend.app.services.http_logging import ai_http_log

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "hello"}}]}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp) as mock_post:
            with patch(
                "backend.app.core.database.SessionLocal"
            ) as MockSession:
                mock_db = MagicMock()
                MockSession.return_value = mock_db

                body = {"model": "gpt-4o", "messages": [{"role": "user", "content": "hi"}]}
                resp = ai_http_log(
                    task_id=42,
                    request_type="text",
                    url="http://api.example.com/chat",
                    request_body=body,
                )

                assert resp.status_code == 200
                assert mock_db.add.called
                log_obj = mock_db.add.call_args[0][0]
                assert log_obj.task_id == 42
                assert log_obj.request_type == "text"
                assert log_obj.url == "http://api.example.com/chat"
                assert log_obj.response_status == 200
                assert log_obj.duration_ms is not None

    def test_image_request_logged(self):
        from backend.app.services.http_logging import ai_http_log

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"data": [{"url": "http://img.example.com/cat.jpg"}]}
        mock_resp.raise_for_status = MagicMock()

        with patch("requests.post", return_value=mock_resp):
            with patch(
                "backend.app.core.database.SessionLocal"
            ) as MockSession:
                mock_db = MagicMock()
                MockSession.return_value = mock_db

                body = {"model": "dall-e-3", "prompt": "a cute cat"}
                resp = ai_http_log(
                    task_id=99,
                    request_type="image",
                    url="http://api.example.com/images",
                    request_body=body,
                )

                log_obj = mock_db.add.call_args[0][0]
                assert log_obj.task_id == 99
                assert log_obj.request_type == "image"
                assert log_obj.duration_ms is not None

    def test_error_logged(self):
        from backend.app.services.http_logging import ai_http_log

        with patch(
            "requests.post", side_effect=Exception("connection refused")
        ):
            with patch(
                "backend.app.core.database.SessionLocal"
            ) as MockSession:
                mock_db = MagicMock()
                MockSession.return_value = mock_db

                body = {"model": "gpt-4o"}
                with pytest.raises(Exception, match="connection refused"):
                    ai_http_log(
                        task_id=1,
                        request_type="text",
                        url="http://api.example.com/chat",
                        request_body=body,
                    )

                log_obj = mock_db.add.call_args[0][0]
                assert "connection refused" in log_obj.error
                assert log_obj.task_id == 1
                assert log_obj.response_status is None


class TestContextVarTaskId:
    def test_context_var_overrides_param(self):
        from backend.app.services.http_logging import (
            ai_http_log,
            get_current_task_id,
            set_current_task_id,
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_resp.raise_for_status = MagicMock()

        token = set_current_task_id(777)
        try:
            with patch("requests.post", return_value=mock_resp):
                with patch(
                    "backend.app.core.database.SessionLocal"
                ) as MockSession:
                    mock_db = MagicMock()
                    MockSession.return_value = mock_db

                    resp = ai_http_log(
                        task_id=1,  # should be overridden by context var 777
                        request_type="text",
                        url="http://api.example.com",
                        request_body={"model": "test"},
                    )
                    log_obj = mock_db.add.call_args[0][0]
                    assert log_obj.task_id == 777
        finally:
            set_current_task_id(None)
