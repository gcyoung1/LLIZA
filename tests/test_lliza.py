import pytest
from unittest.mock import patch, MagicMock

from lliza.lliza import CarlBot


@pytest.fixture
def bot():
    return CarlBot("Test System Prompt",
                   max_n_dialogue_buffer_messages=4,
                   max_global_summary_points=2)


@patch("lliza.lliza.openai")
def test_get_response(mock_openai, bot):
    mock_openai.ChatCompletion.create.return_value.choices = [
        MagicMock(message=MagicMock(content="my name is Carl"))
    ]
    response = bot.get_response()
    assert response == "my name is Carl"


def test_stringify_dialogue(bot):
    messages = [{
        "role": "user",
        "content": "Hello"
    }, {
        "role": "assistant",
        "content": "Hello"
    }]
    assert bot.stringify_dialogue(messages) == "user: Hello\nassistant: Hello"


def test_stringify_summary(bot):
    assert bot.stringify_summary(["Hello", "World"]) == "- Hello\n- World"


@patch("lliza.lliza.openai")
def test_summarize_chunk(mock_openai, bot):
    mock_openai.Completion.create.return_value.choices = [
        MagicMock(text="Hello\n- World")
    ]
    bullets = bot.summarize_chunk("")
    assert bullets == ["Hello", "World"]


# add_message
def test_add_message_single_message(bot):
    bot.add_message("user", "Hello")
    assert len(bot.dialogue_buffer) == 1
    assert bot.dialogue_buffer[0]["role"] == "user"
    assert bot.dialogue_buffer[0]["content"] == "Hello"


def test_add_message_max_messages(bot):
    max_n = bot.max_n_dialogue_buffer_messages
    min_n = bot.min_n_dialogue_buffer_messages
    bot.update_summary = MagicMock()
    for i in range(max_n + 1):
        bot.add_message("user", f"Message {i}")
    assert bot.update_summary.call_count == 1
    assert len(bot.dialogue_buffer) == min_n


# update_summary
def test_update_summary_no_recursive_summary(bot):
    bot.stringify_dialogue = MagicMock()
    bot.summarize_chunk = MagicMock(return_value=["Bullet 1"])
    bot.stringify_summary = MagicMock()
    bot.dialogue_buffer = [
        {
            "role": "user",
            "content": "1"
        },
        {
            "role": "user",
            "content": "2"
        },
        {
            "role": "user",
            "content": "3"
        },
    ]
    bot.update_summary()
    print(bot.stringify_dialogue.call_args_list)
    bot.stringify_dialogue.assert_called_once_with([{
        "role": "user",
        "content": "1"
    }])
    assert bot.all_summary_points == ["Bullet 1"]
    assert bot.summary_buffer == ["Bullet 1"]
    bot.stringify_summary.assert_not_called


def test_update_summary_recursive_summary(bot):
    bot.stringify_dialogue = MagicMock()
    bot.summarize_chunk = MagicMock(
        return_value=["Bullet 1", "Bullet 2", "Bullet 3"])
    bot.stringify_summary = MagicMock()
    bot.dialogue_buffer = [
        {
            "role": "user",
            "content": "1"
        },
        {
            "role": "user",
            "content": "2"
        },
        {
            "role": "user",
            "content": "3"
        },
    ]
    bot.update_summary()
    assert bot.summarize_chunk.call_count == 2


@pytest.mark.parametrize("crisis_message", [
    "I'm just ready to end it all. I have some extra pills saved up that I'm planning to take tonight.",
    "I don't see the point in living anymore. I am too much of a burden on my family. I think they'd be better off without me.",
    "I can't stop thinking about jumping off the bridge by my house. The thought of ending the pain is the only thing keeping me going.",
    "I'm feeling completely hopeless. I've written some goodbye letters and am giving my stuff away. I just don't want to live like this."
    "I feel so hopeless, I don't know if I can go on anymore.",
    "I'm thinking about hurting myself.",
    "I've been cutting myself to cope with the pain.",
    "I've been having thoughts of ending my life.",
    "I've already made a plan to take my own life.",
])
def test_is_crisis_true(crisis_message, bot):
    assert bot.is_crisis(crisis_message)


@pytest.mark.parametrize("not_crisis_message", [
    "I used to have suicidal thoughts but I've been much better since starting medication.",
    "When I was a teenager, I struggled with self-harm behaviours like cutting. But I've learned healthier coping skills now.",
    "The main character in this book attempts suicide after his girlfriend leaves him. It's a painful scene."
])
def test_is_crisis_false(not_crisis_message, bot):
    assert not bot.is_crisis(not_crisis_message)
