"""台本生成（Gemini API）"""

import json
import logging
from typing import Optional

import config

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """あなたはInstagram Reels向け短尺動画の台本ライターです。
以下のテーマで、視聴者を引き込むReels用の動画台本を作成してください。

テーマ: {theme}

■ 構成ルール（必ず守ること）:
1. フック（シーン1）: 最初の2秒で視聴者の注意を引く衝撃的・意外性のある一言。疑問形や「知らないと損」系が有効
2. 展開（シーン2〜N-1）: テーマを具体例・数字・ストーリーで分かりやすく展開
3. CTA（最終シーン）: フォロー・保存・コメントを自然に促すまとめの一言

■ テキストのルール:
- ターゲット: 20〜30代の日本人
- 口調: {tone_instruction}
- 一人称: 「{first_person}」を使うこと
- 二人称: 「{second_person}」を使うこと
- 一文は短く、話し言葉で
- 各シーンの読み上げテキストは該当秒数で読める長さにする

■ 画像プロンプト生成手順（必ずこの順序で考えること）:

【STEP 1: シーン分析】各シーンのテキストから以下を抽出:
- 感情トーン: 不安/希望/驚き/怒り/喜び/悲しみ/緊張/安心 など
- 状況: 何が起きているか、どんな場面か
- 主要な視覚要素: 人物/物/場所/行動
- 時間帯・環境: 朝/昼/夜、室内/屋外、季節 など

【STEP 2: 視覚的表現の決定】分析結果から:
- 感情を表す表情・姿勢・身体言語
- 状況を伝える背景・小道具
- 雰囲気を作る照明・色調

【STEP 3: プロンプト構築】以下の形式で英語記述:
"realistic photograph, vertical 9:16 aspect ratio,
 [人物の表情・姿勢], [状況を示す要素], [背景],
 [照明: 感情に合った照明], [カメラアングル],
 no text, no letters, no watermarks"

■ 感情と照明の対応例:
- 不安・悩み → dim lighting, shadows, muted colors
- 希望・前向き → bright natural light, warm tones
- 驚き・衝撃 → dramatic lighting, high contrast
- 落ち着き・安心 → soft diffused light, neutral tones
- 緊張・焦り → harsh overhead light, cool tones

■ 画像プロンプトの技術要件（Imagen 3向け・必ず英語で記述）:
- 必ず "realistic photograph" を含める
- 構図: "vertical 9:16 aspect ratio" を明記
- カメラアングル・距離を指定（例: close-up, medium shot, overhead view）
- テキスト・文字・ロゴの描画は禁止（"no text, no letters, no watermarks" を末尾に追加）
- 背景・被写体の具体的な描写を含める

■ 制約:
- シーン数: {min_scenes}〜{max_scenes}
- 合計秒数: 約{duration}秒
- 各シーンの秒数は3〜8秒の範囲

以下のJSON形式で出力してください（JSONのみ、説明不要）:
{{
  "title": "動画タイトル",
  "scenes": [
    {{
      "scene_id": 1,
      "text": "読み上げテキスト",
      "image_prompt": "realistic photograph, vertical 9:16 aspect ratio, [detailed scene description], [lighting], [camera angle], no text, no letters, no watermarks",
      "duration_sec": 4
    }}
  ]
}}"""

REFERENCE_IMAGES_INSTRUCTION = """

■ 参考画像について（重要・全シーンに適用）:
添付された参考画像を台本作成の参考にしてください。
- 画像の雰囲気・テーマ・被写体・色調・スタイルを読み取ってください
- 「すべてのシーン」のimage_promptに参考画像のスタイルや雰囲気を一貫して反映させてください（1カット目だけでなく、最初から最後まで全シーン）
- 各シーンのimage_promptに、参考画像から読み取れるトーン（例: 色味、照明の雰囲気、被写体の系統）を統一的に盛り込んでください
- 台本のテキスト内容にも、画像から感じ取れるテーマや世界観を反映させてください
- ただし画像の内容をそのまま説明するのではなく、あくまでインスピレーションとして活用してください"""

REFERENCE_SCRIPT_INSTRUCTION = """

■ 参考台本について（重要）:
以下の参考台本を元に、新しい台本を作成してください。

【参考台本】
{reference_script}

【指示】
- 上記の参考台本の構成・流れ・トーンを参考にしてください
- 内容をそのままコピーするのではなく、上記のテーマに合わせて新しく書き直してください
- 参考台本の「話し方のリズム」「展開の仕方」「視聴者への呼びかけ方」を学んで活用してください
- シーンの区切り方や各シーンの長さ感も参考にしてください
- ただし、image_promptは参考台本に依存せず、テーマに合った新しい画像を生成するためのプロンプトを作成してください"""

MOCK_SCRIPT = {
    "title": "30代転職でやりがちな失敗3選",
    "scenes": [
        {
            "scene_id": 1,
            "text": "30代で転職するとき、これやると失敗します",
            "image_prompt": "Japanese man in his 30s looking worried at office desk, realistic photo, vertical 9:16, soft lighting",
            "duration_sec": 5,
        },
        {
            "scene_id": 2,
            "text": "1つ目、年収だけで転職先を選ぶこと",
            "image_prompt": "Close up of Japanese salary statement on desk with calculator, realistic photo, vertical 9:16",
            "duration_sec": 5,
        },
        {
            "scene_id": 3,
            "text": "2つ目、自己分析をせずに応募すること",
            "image_prompt": "Japanese businessman staring at blank resume paper looking confused, realistic photo, vertical 9:16",
            "duration_sec": 5,
        },
        {
            "scene_id": 4,
            "text": "3つ目、退職してから転職活動を始めること",
            "image_prompt": "Japanese man carrying cardboard box leaving office building, realistic photo, vertical 9:16, dramatic lighting",
            "duration_sec": 5,
        },
        {
            "scene_id": 5,
            "text": "在職中にしっかり準備して、後悔しない転職をしましょう",
            "image_prompt": "Confident Japanese businessman smiling at new modern office, realistic photo, vertical 9:16, bright natural light",
            "duration_sec": 5,
        },
    ],
}


TONE_MAP = {
    "desu_masu": "ですます調（丁寧で親しみやすい口調。例:「〜なんです」「〜ですよね」）",
    "da_dearu": "だ・である調（断定的で力強い口調。例:「〜なんだ」「〜だろう」）",
}

FIRST_PERSON_MAP = {
    "watashi": "私",
    "ore": "俺",
}

SECOND_PERSON_MAP = {
    "anata": "あなた",
}


def _detect_mime_type(data: bytes) -> str:
    """バイト先頭からMIMEタイプを簡易判定する。"""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    # フォールバック
    return "image/jpeg"


def generate_script(
    theme: str,
    duration_sec: int = None,
    mock: bool = False,
    tone: str = None,
    first_person: str = None,
    second_person: str = None,
    reference_images: Optional[list[bytes]] = None,
    reference_script: Optional[str] = None,
) -> dict:
    duration_sec = duration_sec or config.DEFAULT_DURATION_SEC

    if mock:
        logger.info("[MOCK] 台本生成をスキップ（モックデータ使用）")
        return MOCK_SCRIPT

    # --- 本番実装 ---
    from google import genai
    from google.genai.types import Part

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    tone_instruction = TONE_MAP.get(tone or "desu_masu", TONE_MAP["desu_masu"])
    fp = FIRST_PERSON_MAP.get(first_person or "watashi", "私")
    sp = SECOND_PERSON_MAP.get(second_person or "anata", "あなた")

    prompt = PROMPT_TEMPLATE.format(
        theme=theme,
        duration=duration_sec,
        min_scenes=config.SCENE_COUNT_MIN,
        max_scenes=config.SCENE_COUNT_MAX,
        tone_instruction=tone_instruction,
        first_person=fp,
        second_person=sp,
    )

    # 参考台本がある場合はプロンプトに追加
    if reference_script:
        prompt += REFERENCE_SCRIPT_INSTRUCTION.format(reference_script=reference_script)
        logger.info("参考台本をプロンプトに追加（%d文字）", len(reference_script))

    # 参考画像がある場合はマルチモーダル入力を構築
    if reference_images:
        prompt += REFERENCE_IMAGES_INSTRUCTION
        contents = [prompt]
        for img_bytes in reference_images:
            mime = _detect_mime_type(img_bytes)
            contents.append(Part.from_bytes(data=img_bytes, mime_type=mime))
        logger.info("参考画像 %d 枚をマルチモーダル入力に追加", len(reference_images))
    else:
        contents = prompt

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents,
    )

    raw = response.text.strip()
    # JSON部分を抽出（```json ... ``` で囲まれている場合に対応）
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]

    script = json.loads(raw)
    logger.info("台本生成完了: %s（%dシーン）", script["title"], len(script["scenes"]))
    return script
