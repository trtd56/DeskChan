# Gemma 4 Hackathon Notes

このリポジトリは、Cerebras と Google DeepMind による **Gemma 4 24-Hour Hackathon** 用の作業場所です。

元資料: [docs/Gemma 4 Hackathon Instruction Document.pdf](docs/Gemma%204%20Hackathon%20Instruction%20Document.pdf)

## プロジェクト案

**DeskChan StackChan**: StackChanを机の上に置き、カメラで手元・PC・マグカップ・スマホ・照明などを見ながら、低遅延で実況やツッコミを入れる卓上実況ロボのプロトタイプです。

- Gemini Flash-Lite系で事前にプロンプトと構造化出力をテストする
- ハッカソン本番では同じJSONスキーマをCerebras `gemma-4-31b` に差し替える
- StackChanカメラで卓上画像を取得し、作業開始、長時間同じ姿勢、高速タイピング、手が止まる、飲み物、マグカップ危険、スマホ、照明変化などを読む
- Gemini TTS `gemini-3.1-flash-tts-preview` の `Puck` で関西弁の短い実況音声を事前生成し、1.5倍速にしてStackChanが `audio_key` を再生する
- 出力は実況/注意、警戒判定、卓上状態、StackChanの表情/モーション/音声キーに絞る
- 1-2秒ポーリング時は履歴で同じ発話を避け、同じ行動が続く時は黙る/短い実況/雑談に切り替え、長すぎる時だけツッコむ

詳細とデモ時の人間側ストーリー: [docs/stackchan_desk_commentator.md](docs/stackchan_desk_commentator.md)

旧Tetris案: [docs/stackchan_tetris_commentator.md](docs/stackchan_tetris_commentator.md)

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
```

APIキーなしで構造を確認:

```bash
kitchen-chan turn "マグカップがPCの近くにある。短く実況して" --scene desk --provider mock
```

卓上実況UIをローカルで開く:

```bash
kitchen-chan bridge --host 0.0.0.0 --port 8787
```

ブラウザで `http://localhost:8787/` を開きます。

ブラウザUIでは `認識開始` で自動認識を開始し、`認識停止` で停止します。停止ボタンは解析中でも押せるため、デモ中にすぐ止められます。インターバルはStackChanの発話と動きが止まり、短い静止バッファを置いた後から計測します。

自動認識では履歴を見て同じ状態の継続を抑制します。状態が変わらない場合は `*_silence_focus` に差し替えて連続発話と動作を止め、スマホ状態だけは継続を数えた後に一度 `phone_overuse` としてツッコミます。

デモ時の音声はStackChan側で鳴らします。`PC音声プレビュー` は既定OFFのままにし、`音声URL Base` はMacのLAN IP、例 `http://192.168.0.10:8787` を指定します。StackChanがWAVを取得できない場合でも、更新後のファームウェアでは電子音にフォールバックしません。

ハッカソン録画用には `台本デモ` を使います。`greeting` → `work_start` → `typing_fast` → `cup_danger` → `phone_pickup` → `phone_overuse` → `yawn` → `focus_achieved` の順で事前定義セリフを発火します。表の各行の `発火` ボタンで、個別状態だけを鳴らすこともできます。

StackChanブリッジにJSONをPOSTする場合:

```bash
kitchen-chan turn "スマホを手に取った。短く実況して" \
  --scene desk \
  --provider mock \
  --stackchan-url http://stackchan.local/action
```

Gemini Flash-Liteでテスト:

```bash
export GEMINI_API_KEY=...
kitchen-chan turn "StackChanのカメラ画像を見て、卓上作業を実況して" \
  --scene desk \
  --provider gemini \
  --stackchan-camera-url http://192.168.11.15
```

Cerebras/Gemma 4で本番比較:

```bash
export CEREBRAS_API_KEY=...
kitchen-chan compare "カップが机の端に近い。短く実況して" --scene desk --left gemini --right cerebras
```

ブラウザUIの `Provider` で `Cerebras/Gemma 4` を選ぶ場合も `CEREBRAS_API_KEY` が必要です。カメラ画像はOpenAI互換のマルチモーダル形式で、Base64 data URI の `image_url` として `gemma-4-31b` に直接送ります。

Gemini TTSで卓上実況用の事前発話を生成:

```bash
python -m kitchen_chan.tts --input data/desk_voice_lines.json --dry-run
python -m kitchen_chan.tts --input data/desk_voice_lines.json --out public/audio --model gemini-3.1-flash-tts-preview --voice Puck --speed 1.5
```

台本デモの状態定義は `data/desk_demo_states.json`、録音対象の全セリフは `data/desk_voice_lines.json` にあります。

`--speed 1.5` は生成後に `ffmpeg` の `atempo=1.5` で処理します。

## StackChan実機テスト

直接 `http://192.168.11.15/action` へ送るには、現在の公式ファームをHTTPブリッジファームに書き換えます。

ファーム: [firmware/stackchan_http_bridge](firmware/stackchan_http_bridge)

ビルド:

```bash
cd firmware/stackchan_http_bridge
pio run
```

書き込み:

```bash
pio run -t upload --upload-port /dev/cu.usbmodem1101
```

注意: 書き込みは現在の公式StackChanファームを上書きします。`192.168.11.15` に固定するには、2.4GHz Wi-FiのSSID/パスワードを `firmware/stackchan_http_bridge/include/wifi_config.h` に設定してください。

接続候補を確認:

```bash
kitchen-chan device discover
```

現在確認できた候補:

- USB serial: `/dev/cu.usbmodem1101`
- Espressif MAC: `xx:xx:xx:xx:xx:xx`
- HTTP候補: `http://192.168.11.15`

HTTP APIを探す:

```bash
kitchen-chan device probe --url http://192.168.11.15
```

2026-06-28時点の確認では、`/action`, `/speak`, `/api/action` など一般的な直接制御エンドポイントはすべて `404 {"ok":false,"message":"not found"}` でした。接続中の公式ファームは、PCからHTTPで直接操作するAPIではなく、アプリ/クラウド側へWebSocket接続する設計の可能性が高いです。

USBシリアルに試験パケットを送る:

```bash
kitchen-chan device send "デモ紹介して" \
  --scene desk \
  --provider mock \
  --transport serial \
  --port /dev/cu.usbmodem1101
```

シリアルログを見る:

```bash
kitchen-chan device read-serial --port /dev/cu.usbmodem1101 --seconds 5
```

ローカルブリッジでアクションJSONを試す:

```bash
kitchen-chan bridge --host 0.0.0.0 --port 8787
```

別ターミナルから送信:

```bash
kitchen-chan device send "待ち時間に雑談して" \
  --scene desk \
  --provider mock \
  --transport http \
  --url http://127.0.0.1:8787/action
```

ブリッジは `/action` を受け取り、`/audio/<audio_key>.wav` を `public/audio` から配信します。

StackChan側ファームは `../stack_reachy/firmware/stackchan_manzai` の表情描画を参考にした `/face` も持っています。

```bash
curl -X POST http://192.168.11.15/face \
  -H 'Content-Type: application/json' \
  -d '{"face":"retort","source":"画面：ツッコミ顔"}'
```

## 概要

- 主催: Cerebras / Google DeepMind
- 形式: 24時間ハッカソン
- 場所: Cerebras Discord Server `#gemma-4-hackathon`
- 目的: Gemma 4 を Cerebras の高速推論で使い、エージェント、マルチモーダル、エンタープライズ用途などのデモを作る

## スケジュール

PDFでは Pacific Time 表記です。日本時間では以下の通りです。

| 項目 | Pacific Time | 日本時間 |
| --- | --- | --- |
| ハッカソン本編 | 2026-06-28 10:00 - 2026-06-29 10:00 PDT | 2026-06-29 02:00 - 2026-06-30 02:00 JST |
| キックオフ / Q&A | 開始直後30分 | 2026-06-29 02:00頃 JST |
| Private preview access | 2026-06-28 10:30 PDT - 2026-06-29 10:00 PDT | 2026-06-29 02:30 - 2026-06-30 02:00 JST |
| 技術サポート 1 | 2026-06-28 10:30 - 12:30 PDT | 2026-06-29 02:30 - 04:30 JST |
| 技術サポート 2 | 2026-06-29 09:00 - 10:00 PDT | 2026-06-30 01:00 - 02:00 JST |
| 提出締切 | 2026-06-29 10:00 PDT | 2026-06-30 02:00 JST |

事前の capacity increase request form は、PDF上では 2026-06-27 19:00 PT が締切です。

## 賞金トラック

| Track | 内容 | 賞金 |
| --- | --- | --- |
| Track 1 | Multiverse Agents - Best Multi-Agent + Multimodal Use Case | $2,000 |
| Track 2 | People's Choice - Most Impressions on Social Media | $2,000 |
| Track 3 | Enterprise Impact - Best Enterprise Use Case | $1,000 |

複数トラックへの提出が可能です。ただし、各トラックのDiscordチャンネルに個別投稿します。

## 提出方法

提出は、デモ動画とプロジェクト説明を対象トラックのDiscordチャンネルへ投稿します。

- Track 1: `#g4hackathon-multiverse-agents`
- Track 2: `#g4hackathon-people-choice`
- Track 3: `#g4hackathon-enterprise-impact`

Track 2 に出す場合は、X/Twitterにもデモ動画を投稿し、`@Cerebras` と `@googlegemma` をタグ付けします。

締切前であれば、何度でも更新または再提出できます。

## デモ動画要件

- 最大60秒
- Cerebras の高速推論がUXをどう良くするかを明確に見せる
- 推奨: GPUベースの他プロバイダーとのサイドバイサイド比較でレイテンシ差を見せる
- プロジェクトの主要機能、ワークフロー、インパクトに集中する
- 画面録画時は通知、ブラウザタブ、APIキー、メール、認証情報などを映さない

## 審査基準

### Track 1: Multiverse Agents

- 複数AIエージェントの有効な協調
- Gemma 4 31B によるテキスト、画像、動画などの意味あるマルチモーダル活用
- Cerebras の高速推論が体験に与える効果
- Gemma 4 31B を活かした創造性。例: ロボティクス、3Dプリント、スマート製造、自律ラボ、IoT、物理世界との統合

### Track 2: People's Choice

- X/Twitterでのオーガニックインプレッション数
- いいね、コメント、リポスト、議論などのエンゲージメント
- プロジェクトを明確かつ魅力的に見せるコンテンツ品質
- Cerebras + Gemma 4 31B への自然なコミュニティ反応

### Track 3: Enterprise Impact

- エンタープライズ検索、マルチモーダルRAG、インシデント対応、サイバーセキュリティ、カスタマーサポート、ナレッジ管理などの実課題を解く
- スケーラブル、安全、実運用可能な構成
- アーキテクチャと実装品質
- Cerebras の速度と Gemma 4 31B のマルチモーダル能力が、企業体験をどう改善するか

## API / モデル情報

- 利用モデル: Gemma 4 31B
- Model ID: `gemma-4-31b`
- API: 標準の Cerebras Inference API
- エンドポイント: Private preview用の別エンドポイントは不要
- API形式: OpenAI互換の Chat Completions API
- 画像入力: `image_url` による標準OpenAI形式。ホスト画像URLとBase64 data URIに対応
- 出力: テキスト出力
- Structured Outputs / Tool Calling: 対応。`strict: true` によるJSON Schema制約も利用可能
- Reasoning: デフォルトはオフ。`reasoning_effort` に `none`, `low`, `medium`, `high` を指定
- レスポンス情報: `usage` と `time_info` によりトークン数やリクエスト時間を取得可能

専用エンドポイントでは Prometheus 互換メトリクスも提供されます。

- Time to First Token (TTFT)
- Time Per Output Token (TPOT)
- End-to-end latency
- Output tokens per second
- Queue time
- Request success rates

## レート制限 / コンテキスト

ハッカソン中、capacity increase request form を提出した参加者には、以下の elevated API capacity が提供されます。

- 100 RPM
- 100K TPM
- 5K MSL / 32K MCL context

公開無料枠の例としてPDFには `30 RPM / 1M tokens-day` が記載されています。

## 開発ルール

- 既存のscaffolding、boilerplate、開発フレームワークは利用可能
- コア機能はハッカソン中に開発する
- Gemma 4 running on Cerebras をソリューションの中心コンポーネントにする
- Geminiなど別プロバイダーを比較用ベースラインとして呼ぶことは可能
- ただし、主要なモデル実行は Cerebras 上の Gemma 4 にする

## 参加チェックリスト

- [ ] Cerebras Cloud にサインアップする
- [ ] Organization ID を確認する
- [ ] APIキーとPrivate preview accessを確認する
- [ ] `gemma-4-31b` で最小リクエストを通す
- [ ] `time_info` をログに出し、速度をデモで見せられるようにする
- [ ] 60秒以内のデモ動画構成を決める
- [ ] APIキー、通知、個人情報が録画に映らない状態にする
- [ ] 提出するトラックを決める
- [ ] Discordの該当チャンネルへ投稿する
- [ ] Track 2の場合はX/Twitterにも投稿し、`@Cerebras` と `@googlegemma` をタグ付けする
