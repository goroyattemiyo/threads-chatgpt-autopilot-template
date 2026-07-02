# Security Policy

## 認証情報を共有しない

以下の情報を、リポジトリ、Issue、チャット、メール、フォームへ書かないでください。

- GitHub、Meta、Facebook、ChatGPTのパスワード
- Threadsアクセストークン
- GitHub Personal Access Token
- GitHub Secretsの値
- 二段階認証コード
- バックアップコード
- 決済情報

## GitHub Secrets

以下は、利用者本人がPrivate自動投稿リポジトリのGitHub Secretsへ登録します。

- `THREADS_ACCESS_TOKEN`
- `THREADS_USER_ID`
- `ASSETS_REPO_TOKEN`（画像投稿を使う場合のみ）

入力時は画面共有を停止し、入力後の値を第三者へ見せないでください。

## リポジトリの公開範囲

### Private自動投稿リポジトリ

以下を保管します。

- 投稿予定
- 投稿履歴
- GitHub Actions
- 顧客別設定
- GitHub Secrets

### Public画像リポジトリ

Threadsから取得する投稿用画像だけを保管します。

以下を置かないでください。

- 投稿前に見られて困る画像
- 個人情報・機密情報を含む画像
- 投稿予定・投稿本文・投稿履歴
- 認証情報
- 内部マニュアル

## 画像用トークン

`ASSETS_REPO_TOKEN`はFine-grained Personal Access Tokenを使用し、画像用リポジトリ1つだけに`Contents: Read and write`を許可します。

有効期限は必要な期間に限定してください。

## 漏えいが疑われる場合

1. 該当トークンを直ちに失効する
2. 新しいトークンを発行する
3. GitHub Secretsを更新する
4. GitHub Actionsの実行履歴を確認する
5. GitHubのアクセス権とログイン履歴を確認する
6. 必要に応じてパスワードと二段階認証を見直す
7. 発生内容と対応を記録する

## 契約・サポート終了時

- 運営者のリポジトリアクセス権を削除する
- 画像用Personal Access Tokenを失効する
- 不要なSecretsを削除する
- Threadsアクセストークンの更新を検討する
- Public画像リポジトリを残すか削除するか利用者本人が判断する
