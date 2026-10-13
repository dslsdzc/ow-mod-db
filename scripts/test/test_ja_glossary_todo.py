import ja_glossary_todo as jt


def test_render_todo_marks_progress_and_sections():
    zh = {"terms": {"Nomai": "挪麦", "Quantum Moon": "量子卫星"},
          "characters": {"Solanum": "所莱内姆"}}
    ja = {"terms": {"Nomai": "ノマイ"}}
    text = jt.render_todo(zh, ja)
    assert "1 / 3" in text                                  # 进度统计
    assert "| ✅ | Nomai | 挪麦 | ノマイ |" in text          # 已取证打勾
    assert "| ⬜ | Quantum Moon | 量子卫星 | |" in text      # 未取证留空
    assert "## characters" in text and "Solanum" in text


def test_render_todo_handles_empty_glossaries():
    text = jt.render_todo({}, {})
    assert "0 / 0" in text
    assert "本节为空" in text
