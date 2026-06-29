# StackChan Tetris Commentator

## Pitch

TetrisChan StackChan is a physical AI commentator for Tetris. A camera watches the game screen, a multimodal model reads the board, and StackChan reacts with short Kansai-dialect play-by-play, tactical nudges, expressions, motion, and pre-generated voice clips.

The demo target is not a generic game assistant. It is a low-latency embodied commentator that makes fast board-state changes feel visible, funny, and useful.

## Hackathon Fit

- Track focus: Track 1, Multiverse Agents.
- Physical AI: StackChan is the embodied commentator beside the player or screen.
- Multimodal: camera frame of the game screen plus text prompt, history, latency, and structured output.
- Speed story: test the same structured prompt with Gemini Flash-Lite before Cerebras access opens, then switch to Cerebras `gemma-4-31b`.
- Comparison story: side-by-side recording of Gemini Flash-Lite and Cerebras/Gemma 4 on the same Tetris frame, showing response latency and whether the comment still arrives before the board changes.

## Product Shape

The MVP watches a Tetris screen and returns one short spoken reaction per turn:

1. Capture a frame from StackChan camera or local test image.
2. Gemini Flash-Lite reads the board during pre-hackathon testing.
3. Cerebras/Gemma 4 uses the same JSON schema during the private preview.
4. StackChan receives an action packet: expression, motion, intensity, and `audio_key`.
5. Audio is played from pre-generated Gemini TTS WAV files, so physical timing is stable even when model latency varies.

## Agent Roles

- Vision Agent: identifies board height, holes, well, hold, next queue, ghost piece, line clears, incoming garbage, and top-out state.
- Strategy Agent: picks the immediate tactic: hold, rotate, move, hard drop, keep well open, recover, clear lines, or attack.
- Banter Agent: turns the tactic into a short Kansai-dialect line with an appropriate StackChan expression and voice key.

For the hackathon demo, these are represented in a single structured model call for speed. If time allows, split them into parallel calls and merge votes.

## StackChan Action Packet

```json
{
  "reply": "右端の井戸は空けとこ。そこ埋めたら、未来の自分から苦情くるで。",
  "safety_level": "ok",
  "game_phase": "stacking",
  "stackchan": {
    "expression": "happy",
    "motion": "nod",
    "audio_key": "tetris_keep_well_open",
    "intensity": 2
  },
  "actions": ["Keep the right well open."],
  "timers": [],
  "visual_checklist": ["盤面の高さ", "右端の井戸", "ホールド", "ネクスト"],
  "agent_notes": [
    {"agent": "vision", "vote": "right well is open"},
    {"agent": "strategy", "vote": "stack left and preserve well"},
    {"agent": "banter", "vote": "tetris_keep_well_open"}
  ],
  "demo_caption": "StackChanが盤面を見て、実況と次の一手を即答します。"
}
```

## Model Plan

- Development baseline: Gemini Flash-Lite for image plus structured JSON output.
- Hackathon primary: Cerebras OpenAI-compatible Chat Completions with `gemma-4-31b`.
- TTS: Gemini TTS preview, pre-generated with the `Puck` voice to `public/audio/*.wav`, then post-processed to 1.5x speed.
- Cerebras fallback: if image input is not available through the current path, use Gemini Flash-Lite for frame-to-board summary and send that board summary to Cerebras/Gemma 4 for the final commentary.

## Voice Direction

Use a cheerful Kansai Japanese character. The teasing should target board state and timing, not the player's identity or ability.

Good:

- "右端の井戸は空けとこ。そこ埋めたら、未来の自分から苦情くるで。"
- "積み上がりすぎや。消せる列を優先して、Tetris欲張りはいったん封印や。"

Avoid:

- Personal insults about the player.
- Long lectures.
- Overconfident exact moves when the camera image is blurry, cropped, or dark.

## 60 Second Demo Script

1. 0-6s: show StackChan beside a Tetris screen and the vision UI receiving a camera frame.
2. 6-14s: Gemini Flash-Lite returns structured commentary and latency.
3. 14-24s: StackChan reacts with `tetris_keep_well_open` or `tetris_next_piece`.
4. 24-34s: show a dangerous high stack; model switches to `safety_level: warn`.
5. 34-44s: show a line clear or Tetris opportunity; StackChan celebrates or calls the setup.
6. 44-54s: compare Gemini Flash-Lite and Cerebras/Gemma 4 on the same frame.
7. 54-60s: final caption: "高速推論で、テトリスのツッコミが間に合う。"

## 人間側デモストーリー

| 時間 | 人間側の動き | StackChan / アプリの反応 | 見せるポイント |
| --- | --- | --- | --- |
| 0-4秒 | StackChanを画面横に置き、テトリス盤面をカメラに入れる。 | `tetris_demo_intro` | ただの画面解析ではなく、物理実況者だと分かる。 |
| 4-10秒 | 低い盤面でプレイ開始。右端井戸が空いた状態を見せる。 | `tetris_keep_well_open` | 盤面の形を読んで短く助言する。 |
| 10-18秒 | ネクストやホールドが映るように画角を整える。 | `tetris_next_piece` または `tetris_hold_now` | 二手先を見る実況にする。 |
| 18-26秒 | わざと高く積む、または井戸を塞ぐ。 | `tetris_danger_high_stack` または `tetris_well_blocked_warn` | `safety_level: warn` と表情変化を見せる。 |
| 26-34秒 | 一列または二列消して復旧する。 | `tetris_recover` または `tetris_close_call` | 危険から回復する流れを見せる。 |
| 34-42秒 | Iミノ待ちやT-spin形を作る。 | `tetris_ready_tetris` または `tetris_tspin_setup` | 攻撃機会を実況する。 |
| 42-52秒 | 同じフレームをGemini Flash-LiteとCerebras/Gemma 4で比較。 | `tetris_demo_compare` | 低レイテンシがゲーム実況体験に効くことを見せる。 |
| 52-60秒 | StackChanと画面を同時に映し、最後の一言を再生。 | `tetris_demo_final_line` | 締め: 「高速推論で、テトリスのツッコミが間に合う。」 |

## 差し替え用の小ネタ

- 画面が暗い: `tetris_photo_too_dark`
- 画面がブレる: `tetris_photo_blurry`
- 置きミス: `tetris_misdrop`
- 高く積みすぎ: `tetris_danger_high_stack`
- 井戸を塞ぐ: `tetris_well_blocked_warn`
- Tetrisチャンス: `tetris_ready_tetris`
- 速度比較を説明: `tetris_demo_latency_joke`

## 撮影カット

- 引きの画: StackChan、ゲーム画面、プレイヤーの手元が全部見える。
- 寄りの画: 盤面、ホールド、ネクストが読める。
- 画面録画: `audio_key`、`safety_level`、`game_phase`、レイテンシ入りの構造化JSON。
- リアクションカット: 事前生成音声に合わせてStackChanが動く。
- 比較カット: 同じ盤面で Gemini Flash-Lite と Cerebras/Gemma 4 のレスポンス時間を並べる。
