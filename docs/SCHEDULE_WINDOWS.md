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

## 設定の正本

投稿時刻は`config/service.yml`だけで管理します。

```yaml
posting:
  time_slots:
    morning: "07:00"
    night: "20:00"

  schedule_offsets_minutes:
    - -3
    - 2
    - 7
```

`time_slots`または`schedule_offsets_minutes`を変更してmainブランチへ反映すると、`Sync Posting Schedule` workflowが起動します。

同期処理は次を行います。

1. `service.timezone`を読み取る
2. 投稿時刻と相対分をUTCへ変換する
3. 重複するcronを統合する
4. `.github/workflows/post-due.yml`の自動生成範囲だけ更新する
5. 差分がある場合だけGitHub Actions botがコミットする

利用者やAIが`post-due.yml`のcronを直接編集する必要はありません。

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

## 新しい時刻を追加する例

JST 10:00を追加する場合は、`config/service.yml`だけを変更します。

```yaml
posting:
  time_slots:
    morning: "07:00"
    late_morning: "10:00"
    night: "20:00"
```

同期後、09:57・10:02・10:07 JSTに対応するUTC cronが自動生成されます。

## 顧客別の最適化

顧客が実際に使う投稿枠だけ残します。

20:00だけ使う場合は1日3回、月約90回です。
既定6枠をすべて使う場合は1日18回、月約540回です。

## 手動同期と確認

必要な場合は`Sync Posting Schedule`をActions画面から手動実行できます。

ローカルまたはCIで同期状態だけ確認する場合：

```bash
python -m src.sync_post_schedule --check
```

設定とworkflowがずれている場合は失敗します。

## 運用上の注意

- `config/service.yml`を投稿時刻の唯一の正本とする
- 自動生成マーカー内を手作業で編集しない
- Scheduled Runが遅れる可能性を利用者へ説明する
- 「指定時刻ぴったり」を保証しない
- 手動実行成功とScheduled実行成功を分けて検証する
- 顧客が使わない投稿枠は削除してActions使用量を抑える
- 同期workflow失敗時は`post-due.yml`を手修正せず、ログと権限を確認する
