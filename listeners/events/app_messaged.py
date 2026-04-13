import os
import urllib.request

from ai.ai_constants import DM_SYSTEM_CONTENT
from ai.providers import get_provider_response
from logging import Logger
from slack_bolt import BoltContext, Say
from slack_sdk import WebClient
from ..listener_utils.listener_constants import DEFAULT_LOADING_TEXT
from ..listener_utils.parse_conversation import parse_conversation

"""
Handles message events for the bot. Responds in DMs, and in channels/groups where the bot
is a member it replies in a thread to every user message. Threaded replies continue the
conversation in the same thread. Messages that include file attachments are not sent to
the AI; the attached files are downloaded to the project's ``download/`` directory instead.
"""

# Project-root/download. This file lives at listeners/events/app_messaged.py,
# so go up two levels to reach the repo root.
_DOWNLOAD_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "download")
)


def _download_slack_file(file_info: dict, client: WebClient, token: str, dest_dir: str):
    """Download a single Slack file object to ``dest_dir``.

    Returns the saved absolute path, or ``None`` if the file had no download URL.
    Slack's private file URLs require a bearer token on the request.

    The ``files`` entries in a ``message`` event are often only stubs (see
    ``file_access == 'check_file_info'``) without ``url_private``. In that case we
    fetch the full file metadata via ``files.info`` before downloading.
    """
    url = file_info.get("url_private_download") or file_info.get("url_private")

    # Stub detection: Slack sometimes sends minimal file info and expects us to
    # call files.info to retrieve the real metadata (including URLs).
    if not url or file_info.get("file_access") == "check_file_info":
        file_id = file_info.get("id")
        if not file_id:
            return None
        info_resp = client.files_info(file=file_id)
        full_info = info_resp.get("file") or {}
        # Prefer freshly fetched values over the stub.
        file_info = {**file_info, **full_info}
        url = file_info.get("url_private_download") or file_info.get("url_private")
        if not url:
            return None

    file_id = file_info.get("id") or ""
    name = file_info.get("name") or f"{file_id or 'file'}.bin"
    # Prefix with file_id so concurrent uploads with the same name don't collide.
    safe_name = f"{file_id}_{name}" if file_id else name
    dest_path = os.path.join(dest_dir, safe_name)
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp, open(dest_path, "wb") as out:
        out.write(resp.read())
    return dest_path


def app_messaged_callback(
    client: WebClient,
    event: dict,
    logger: Logger,
    say: Say,
    context: BoltContext,
):
    print("Received message event:", event)

    # Ignore bot messages to prevent infinite loops.
    if event.get("bot_id"):
        return

    # Ignore noisy subtypes (edits, joins, deletes, etc.), but allow file uploads
    # (subtype == "file_share") through so we can save attachments to disk below.
    subtype = event.get("subtype")
    if subtype is not None and subtype != "file_share":
        return

    channel_id = event.get("channel")
    thread_ts = event.get("thread_ts")
    user_id = event.get("user")
    text = event.get("text") or ""
    channel_type = event.get("channel_type")
    bot_user_id = context.bot_user_id

    # Skip the bot's own user messages just in case.
    if user_id and bot_user_id and user_id == bot_user_id:
        return

    is_dm = channel_type == "im"

    # In channels/groups, if the bot is @mentioned, let app_mention handler
    # process it to avoid duplicate responses.
    if not is_dm and bot_user_id and f"<@{bot_user_id}>" in text:
        return

    # Decide which thread_ts to reply in:
    # - DMs: keep current behavior (only thread if user already in a thread)
    # - Channels: always reply in thread (use existing thread or start one on this message)
    if is_dm:
        reply_thread_ts = thread_ts
    else:
        reply_thread_ts = thread_ts or event.get("ts")

    # If the message has file attachments, download them to ``download/`` and
    # skip AI processing entirely. Any accompanying text is ignored here.
    files = event.get("files") or []
    if files:
        message_ts = event.get("ts")
        all_succeeded = True
        try:
            os.makedirs(_DOWNLOAD_DIR, exist_ok=True)
            token = client.token
            for f in files:
                try:
                    saved_path = _download_slack_file(f, client, token, _DOWNLOAD_DIR)
                    if saved_path:
                        logger.info(f"Saved Slack file to {saved_path}")
                    else:
                        all_succeeded = False
                        logger.warning(
                            f"Skipped Slack file {f.get('id')}: no download URL"
                        )
                except Exception as file_err:
                    all_succeeded = False
                    logger.error(
                        f"Failed to download Slack file {f.get('id')}: {file_err}"
                    )
        except Exception as e:
            all_succeeded = False
            logger.error(f"Error while handling file upload: {e}")

        # React to the original message to signal success/failure.
        if channel_id and message_ts:
            reaction_name = "white_check_mark" if all_succeeded else "x"
            try:
                client.reactions_add(
                    channel=channel_id, name=reaction_name, timestamp=message_ts
                )
            except Exception as react_err:
                logger.error(f"Failed to add reaction {reaction_name}: {react_err}")
        return

    waiting_message = None
    try:
        # Build conversation context from the thread when applicable.
        conversation_context = ""
        if thread_ts:
            conversation = client.conversations_replies(
                channel=channel_id, limit=10, ts=thread_ts
            )["messages"]
            conversation_context = parse_conversation(conversation[:-1])

        waiting_message = say(text=DEFAULT_LOADING_TEXT, thread_ts=reply_thread_ts)

        if is_dm:
            response = get_provider_response(
                user_id, text, conversation_context, DM_SYSTEM_CONTENT
            )
        else:
            response = get_provider_response(user_id, text, conversation_context)

        client.chat_update(
            channel=channel_id, ts=waiting_message["ts"], text=response
        )
    except FileNotFoundError:
        # User has not selected a provider in App Home yet.
        guidance = (
            "사용할 AI provider를 먼저 선택해 주세요. "
            "Slack 사이드바에서 이 봇을 클릭하고 *Home* 탭에서 provider / model을 선택하면 "
            "이후 메시지에 자동으로 답변드립니다."
        )
        if waiting_message:
            client.chat_update(
                channel=channel_id, ts=waiting_message["ts"], text=guidance
            )
    except Exception as e:
        logger.error(e)
        if waiting_message:
            client.chat_update(
                channel=channel_id,
                ts=waiting_message["ts"],
                text=f"Received an error from Bolty:\n{e}",
            )
