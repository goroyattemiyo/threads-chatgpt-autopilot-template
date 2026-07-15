# Threadsアカウント安全ロック

## 目的

Threadsまたは関連するMetaアカウントで、利用停止、審査、権限制限、投稿結果不明などを確認したときに、後続の本番投稿を止めるための手動安全ロックです。

通常時の投稿数や投稿間隔を一律に制限する機能ではありません。明確な異常を確認したときだけ使用します。

## 設定

`config/service.yml`の次の項目を使用します。

```yaml
account_safety:
  posting_locked: false
  lock_reason: ""
```

- `posting_locked: true`：本番投稿を停止する
- `posting_locked: false`：安全ロックを解除する
- `lock_reason`：確認中の理由を、機密情報を含めずに記録する

パスワード、アクセストークン、GitHubトークン、Secrets、二段階認証コードは`lock_reason`へ書かないでください。

## ロック中の動作

- Scheduled実行と手動本番実行は、Threads APIへ投稿せず終了する
- `dry run`は実行できる
- 投稿予定と履歴の確認は続けられる
- `posting.enable_threads: true`でも、安全ロックを優先する
- ロックの解除は自動では行わない

## 安全ロックを有効にする例

次のような場合に使用します。

- ThreadsまたはInstagram側で利用停止、審査、権限制限を確認した
- 投稿されたかどうか分からない
- 台帳とThreads実画面が一致しない
- 二重投稿のおそれがある
- 認証エラーやAPIエラーが連続し、影響を判断できない

設定例：

```yaml
account_safety:
  posting_locked: true
  lock_reason: "Threads account review in progress"
```

## 解除前の確認

固定の停止日数は設けません。次を確認してから、利用者または運営者が明示的に解除します。

1. 利用者本人がThreadsと関連するInstagramのアカウント状態を確認する
2. 未解決の利用停止、審査、異議申し立てがないことを確認する
3. Threads実画面と投稿台帳を照合する
4. `Test Threads Connection`でプロフィール取得を確認する
5. dry runで対象投稿、日時、本文を確認する
6. 必要に応じて本番投稿を1件だけ実行する
7. Threads実画面、投稿ID、履歴、Actions結果が一致することを確認する

確認後：

```yaml
account_safety:
  posting_locked: false
  lock_reason: ""
```

## 使い勝手に関する方針

- 推測による日次投稿上限は設定しない
- 推測による固定待機期間は設定しない
- 投稿集中や類似投稿は、原則として警告・確認対象とする
- 通常の投稿計画を過度に妨げない
- 明確な異常、投稿結果不明、二重投稿のおそれがある場合だけ停止する

## 注意

このロックは、Metaによるアカウント制限や審査を完全に防ぐ機能ではありません。異常確認後の被害拡大や不要な再実行を防ぐための仕組みです。
