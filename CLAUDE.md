# Claudeチャット／Claude Code 作業ルール

このリポジトリを通常のClaudeチャットまたはClaude Codeで操作するときは、最初に`AGENTS.md`を読み、そこに記載された共通ルールを必ず守ってください。

`AGENTS.md`を、投稿予定・投稿履歴・画像・ツリー投稿を扱う際の共通ルールの正本とします。

## 対応するClaude環境

### 通常のClaudeチャット

公式GitHub MCPコネクタを接続し、対象リポジトリへ必要な書き込み権限が付与されている場合、YAMLファイルの作成・更新、検索、Issue・Pull Request・GitHub Actions操作が可能です。

読み取り専用接続ではファイルを変更しないでください。権限不足の場合は、勝手に別の方法を試さず、利用者へ必要な権限を説明してください。

### Claude Code

ローカル、ブラウザ、IDE等のClaude Code環境から、同じ投稿台帳を管理します。

## 主な役割

- Threads投稿予定の追加
- 未投稿データの日時変更
- 投稿予定のキャンセル
- 投稿予定・投稿履歴の検索
- 類似投稿・重複投稿の確認
- 画像付き投稿とツリー投稿のYAML作成
- GitHub Actionsの実行結果確認
- 利用者から明示された場合のみ、PythonやGitHub Actionsの修正

## 作業開始時

1. `AGENTS.md`を読む
2. `config/service.yml`でタイムゾーンと投稿枠を確認する
3. 対象期間の`posts/schedules/`を確認する
4. `posts/posted_log.yml`で過去投稿と重複を確認する
5. 変更対象を`posts/`または`config/service.yml`へ限定する
6. 通常のClaudeチャットでは、対象リポジトリと権限範囲を確認する

通常の投稿管理依頼では、`src/`、`.github/workflows/`、`SECURITY.md`を変更しないでください。

## 投稿時刻とGitHub Actions

- `config/service.yml`の`posting.time_slots`を投稿時刻の正本とします。
- GitHub Actionsを24時間5分間隔では動かしません。
- 既定では各投稿時刻の3分前、2分後、7分後だけ起動します。
- `time_slots`または`schedule_offsets_minutes`を変更してmainへ反映すると、`Sync Posting Schedule`が`post-due.yml`のcronを自動更新します。
- Claudeは通常、投稿時刻変更時に`.github/workflows/post-due.yml`を直接編集しません。
- 設定変更後は`Sync Posting Schedule`と`Test Posting Schedule Sync`の結果を確認してください。
- GitHub Actionsのscheduleは遅れる場合があるため、指定時刻ちょうどの投稿を保証しません。

## 自動投稿直前の安全確認

`status: ready`へ変更すると、設定時刻との関係によっては次回のGitHub Actions実行で投稿される可能性があります。

以下の場合は、勝手に`ready`へ変更せず`draft`で保存し、利用者へ確認してください。

- 投稿時刻がすでに到来している
- 投稿時刻まで30分以内
- 日時または本文が曖昧
- 同じ投稿枠に別の`ready`投稿がある
- 類似投稿または重複投稿が見つかった
- 画像付き投稿で`image_url`が空
- ツリー内の画像URLが揃っていない

## 投稿済みデータ

- `status: posted`の投稿を編集しない
- `threads_post_id`と`thread_post_ids`を削除しない
- 投稿済み内容を再利用するときは、新しいIDで新規予定を作る
- 実際のThreads投稿と履歴が一致しなくなる変更をしない

## GitHub操作

- 変更前に対象ファイルを確認する
- 変更は必要最小限にする
- コミット前に差分を確認する
- 投稿データ変更とプログラム変更を同じコミットへ混ぜない
- 利用者から依頼されていないファイルを整形・移動しない
- コミットメッセージにはパスワード、トークン、個人情報を含めない
- IssueやPull Requestへ認証情報を記載しない
- GitHub Actionsを実行する場合は、dry runか本実行かを明確に確認する

## 認証情報

次を表示、検索、推測、ファイル保存、コミットしないでください。

- Threadsアクセストークン
- GitHub Personal Access Token
- GitHub Secretsの値
- パスワード
- 二段階認証コード
- バックアップコード

認証情報が会話やファイルに含まれている可能性がある場合は、作業を中止し、失効・再発行を利用者へ案内してください。

## 完了報告

作業後は、次を簡潔に報告してください。

- 使用したClaude環境
- 変更したファイル
- 追加・変更した投稿ID
- 投稿日時と投稿枠
- 最終ステータス
- 重複確認の結果
- GitHub Actionsを操作したか
- 利用者が確認すべき点

Secretsやトークンの値は報告へ含めないでください。
