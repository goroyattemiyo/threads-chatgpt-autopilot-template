# 投稿データ形式

投稿予定はYAMLのリストとして管理します。

推奨保存先：`posts/schedules/YYYY-MM-DD_to_YYYY-MM-DD.yml`

## テキスト投稿

```yaml
- id: post_20260703_0700_001
  date: "2026-07-03"
  time_slot: morning
  title: 朝の投稿
  text: |-
    ここに投稿本文を書きます。
  status: ready
  threads_post_id: ""
  posted_at: ""
  error: ""
```

## 画像付き投稿

```yaml
- id: post_20260703_2000_001
  date: "2026-07-03"
  time_slot: evening
  title: 画像付き投稿
  text: |-
    画像付きの投稿です。
  image_key: post_20260703_2000_001
  image_url: ""
  alt: 投稿画像の説明
  local_webp: ""
  image_uploaded_at: ""
  status: draft
  threads_post_id: ""
  posted_at: ""
  error: ""
```

## ツリー投稿

```yaml
- id: post_20260704_1200_001
  date: "2026-07-04"
  time_slot: noon
  title: 3連投の例
  text: |-
    1件目の本文です。
  status: ready
  threads_post_id: ""
  thread_post_ids: []
  posted_at: ""
  error: ""
  thread_posts:
    - text: |-
        2件目の本文です。
      image_key: ""
      image_url: ""
      alt: ""
    - text: |-
        3件目の本文です。
      image_key: ""
      image_url: ""
      alt: ""
```

## 主な項目

| 項目 | 必須 | 説明 |
|---|---:|---|
| `id` | 推奨 | 投稿を識別する一意の文字列 |
| `date` | 必須 | 投稿日。YYYY-MM-DD |
| `time_slot` | 必須 | 設定ファイルで定義した投稿枠 |
| `title` | 任意 | 管理用タイトル |
| `text` | 必須 | 投稿本文 |
| `image_key` | 画像時 | 画像ファイル名から拡張子を除いた値 |
| `image_url` | 画像時 | 外部から取得できる公開URL |
| `alt` | 推奨 | 画像の代替テキスト |
| `thread_posts` | 任意 | 返信として連結する投稿のリスト |
| `status` | 必須 | 投稿状態 |
| `threads_post_id` | 自動 | 投稿成功後に記録されるID |
| `thread_post_ids` | 自動 | 返信投稿のID一覧 |
| `posted_at` | 自動 | 投稿成功日時 |
| `error` | 自動 | 投稿失敗時の原因 |

## ステータス

| status | 意味 |
|---|---|
| `draft` | 準備中 |
| `ready` | 投稿可能 |
| `posted` | 投稿済み |
| `error` | 投稿失敗 |
| `cancelled` | 取り消し |

投稿対象は、指定日時と投稿枠が一致し、`status: ready`で、`threads_post_id`が空の項目に限定します。
