# GitHub Actionsの投稿時間帯設計

## 基本方針

GitHub Actionsを24時間5分間隔で起動しません。
投稿予定時刻の前後だけ、3回に絞って起動します。

標準は次の3回です。

- 投稿予定時刻の3分前
- 投稿予定時刻の2分後
- 投稿予定時刻の7分後

GitHub Actionsの`schedule`は遅延する場合があり、指定分ちょうどの実行を保証しません。
投稿処理は、`scheduled_at`または`publish_after`を過ぎた最初のScheduled Runで行います。

## テンプレート既定枠

`config/service.yml`の既定枠は次の6つです。

| 枠 | JST | 起動時刻（JST） |
|---|---:|---|
| morning | 07:00 | 06:57 / 07:02 / 07:07 |
| noon | 12:00 | 11:57 / 12:02 / 12:07 |
| afternoon | 15:00 | 14:57 / 15:02 / 15:07 |
| evening | 17:00 | 16:57 / 17:02 / 17:07 |
| night | 20:00 | 19:57 / 20:02 / 20:07 |
| summary | 21:00 | 20:57 / 21:02 / 21:07 |

## 重要：投稿枠とcronは自動同期しない

GitHub Actionsのcronは`.github/workflows/post-due.yml`へ固定記述されます。
`config/service.yml`へ新しい投稿枠を追加しただけでは、その時刻のScheduled Runは増えません。

投稿枠を追加・変更・削除するときは、必ず次の2ファイルを同時に確認します。

1. `config/service.yml`
2. `.github/workflows/post-due.yml`

## 新しい時刻を追加する例

JST 10:00の投稿枠を追加する場合、起動候補は次の3回です。

- 09:57 JST = 00:57 UTC
- 10:02 JST = 01:02 UTC
- 10:07 JST = 01:07 UTC

workflowへ追加する例：

```yaml
on:
  schedule:
    - cron: '57 0 * * *'
    - cron: '2,7 1 * * *'
```

既存cronと同じUTC時刻へまとめられる場合は、時・分のリストへ統合します。

## 顧客別の最適化

顧客が実際に使う投稿枠だけ残します。

例：20:00だけ使う場合

```yaml
on:
  schedule:
    - cron: '57 10 * * *'
    - cron: '2,7 11 * * *'
```

この場合は1日3回、月約90回です。
既定6枠をすべて使う場合は1日18回、月約540回です。

## 運用上の注意

- 0分ちょうどのcronは避ける
- Scheduled Runが遅れる可能性を利用者へ説明する
- 「指定時刻ぴったり」を保証しない
- 手動実行成功とScheduled実行成功を分けて検証する
- 投稿枠を増やした際はcron追加漏れを確認する
- 不要な投稿枠のcronは削除してActions使用量を抑える
