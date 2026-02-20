# Instagram Video Generator

テーマを入力するだけで、Instagram Reels向けの短尺動画を自動生成するツールです。

## 機能

- **台本自動生成** - Gemini 2.5 Flash でテーマに沿った台本を生成
- **画像生成** - Gemini 2.5 Flash Image で各シーンの画像を生成
- **動画生成** - Google Veo 2 で画像から動画を生成（全シーン並列処理）
- **音声生成** - Fish Audio TTS でナレーション音声を生成
- **テロップ** - 明朝体・シャドウ付きのテロップを追加可能
- **最終合成** - FFmpeg で動画・音声・テロップを合成

## デモ

![demo](demo.gif)

## セットアップ

### 必要なもの

- Python 3.9+
- Node.js 18+
- FFmpeg
- Google AI Studio API キー（Gemini, Veo2）
- Fish Audio API キー

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/YOUR_USERNAME/instagram-video-gen.git
cd instagram-video-gen

# Python依存関係をインストール
pip install -r requirements.txt

# フロントエンド依存関係をインストール
cd frontend
npm install
cd ..

# 環境変数を設定
cp .env.example .env
# .env ファイルを編集してAPIキーを設定
```

### 環境変数

`.env` ファイルに以下を設定:

```
GEMINI_API_KEY=your_gemini_api_key
FISH_AUDIO_API_KEY=your_fish_audio_api_key
```

## 起動方法

```bash
# バックエンドを起動（ポート8000）
python -m uvicorn server.app:app --reload --port 8000

# 別ターミナルでフロントエンドを起動（ポート3000）
cd frontend
npm run dev
```

ブラウザで http://localhost:3000 にアクセス

## 使い方

1. テーマを入力（例：「30代 転職 失敗」）
2. 台本を確認・編集
3. 画像を確認・再生成
4. 動画を確認・再生成
5. 音声を確認・調整
6. テロップON/OFF、音声間隔を設定
7. 最終動画を書き出し

## 技術スタック

- **バックエンド**: Python, FastAPI
- **フロントエンド**: Next.js 15, React, TypeScript, Tailwind CSS
- **AI**: Google Gemini 2.5 Flash, Veo 2
- **TTS**: Fish Audio
- **動画処理**: FFmpeg

## ライセンス

MIT License
