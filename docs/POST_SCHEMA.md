# 投稿データ形式

投稿予定は`posts/schedules/YYYY-MM-DD_to_YYYY-MM-DD.yml`のYAMLリストで管理します。

## 推奨形式

```yaml
- id: post_20260706_0700_001
  series_id: campaign_a
  title: 朝の投稿
  text: |-
    ここに投稿本文を書きます。
  scheduled_at: '2026-07-06T07:00:00+09:00'
  delay_min_minutes: 2
  delay_max_minutes: 14
  status: ready
  threads_post_id: ''
  thread_post_ids: []
  posted_at: ''
  error: ''
```

`ready`または`posting`を初めて確認したとき、システムが遅延を一度だけ抽選して次を保存します。

```yaml
delay_minutes: 9
publish_after: '2026-07-06T07:09:00+09:00'
```

`publish_after`が存在する場合は再抽選しません。Actionsが起動するたびに時刻を後ろへずらす処理は行いません。

## 画像付き投稿

```yaml
- id: post_20260706_2000_001
  title: 画像付き投稿
  text: |-
    画像付きの投稿です。
  scheduled_at: '2026-07-06T20:00:00+09:00'
  delay_min_minutes: 2
  delay_max_minutes: 14
  image_key: post_20260706_2000_001
  image_url: ''
  alt: 投稿画像の説明
  status: draft
  threads_post_id: ''
  thread_post_ids: []
  posted_at: ''
  error: ''
```

`image_key`があるのに`image_url`が空の場合は`ready`へ変更しません。

## ツリー投稿

```yaml
- id: post_20260706_1200_001
  series_id: guide_01
  title: 3連投の例
  text: |-
    1件目の本文です。
  scheduled_at: '2026-07-06T12:00:00+09:00'
  delay_min_minutes: 2
  delay_max_minutes: 14
  thread_delay_min_seconds: 8
  thread_delay_max_seconds: 25
  status: ready
  threads_post_id: ''
  thread_post_ids: []
  thread_posts:
    - text: |-
        2件目の本文です。
    - text: |-
        3件目の本文です。
```

ツリーは1回のActions内で直列投稿します。各返信は直前の投稿IDを`reply_to_id`として使用します。

処理中は次の進捗を保存します。

```yaml
status: posting
thread_progress:
  root_post_id: '...'
  reply_ids:
    - '...'
  completed_replies: 1
  updated_at: '2026-07-06T07:12:34+09:00'
```

返信途中で失敗した場合は`status: error`になります。原因修正後に`ready`へ戻すと、保存済みの親投稿・返信は再送せず、未完了返信から再開します。

## 後方互換

`scheduled_at`がない既存データは、`date + time_slot`から変換します。

| time_slot | JST |
|---|---:|
| morning | 07:00 |
| noon | 12:00 |
| afternoon | 15:00 |
| evening | 17:00 |
| night | 20:00 |
| summary | 21:00 |

変換後は`scheduled_at`、`delay_minutes`、`publish_after`をYAMLへ保存します。

## シリーズ順序

同じ`series_id`で後続投稿がすでに`posted`の場合、それより古い未投稿は定期実行から除外します。意図的に解除する場合だけ次を設定します。

```yaml
allow_out_of_order: true
```

またはGitHub Actionsの手動実行で対象`post_id`を明示します。

## ステータス

| status | 意味 |
|---|---|
| draft | 準備中・保留 |
| ready | 投稿可能 |
| posting | 親投稿またはツリー処理中 |
| posted | 正常完了 |
| error | 自動再試行しない失敗状態 |
| cancelled | 取り消し |

定期実行の候補は`ready`または`posting`で、`publish_after`が現在時刻以前の投稿です。一度の実行で処理する親投稿は1件だけです。
