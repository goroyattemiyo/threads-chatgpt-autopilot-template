# テンプレート初期設定

この文書は、顧客ごとのThreads自動投稿リポジトリを作成するときの初期設定手順です。

> 現在はv0.1の構築中です。販売前テストが完了するまでは本番アカウントで使用しないでください。

## 1. 顧客所有のリポジトリを作る

このテンプレートから、顧客本人のGitHubアカウントにPrivateリポジトリを作成します。

推奨名：

```text
threads-autopilot
```

投稿予定、投稿履歴、GitHub Actions、設定はこのPrivateリポジトリで管理します。

## 2. `config/service.yml`を変更する

最低限、以下を顧客環境へ合わせます。

- `service.timezone`
- `threads.account_label`
- `posting.time_slots`
- `posting.enable_images`
- `assets.repository`（画像投稿を利用する場合）

アクセストークンやパスワードは、このファイルへ書かないでください。

## 3. GitHub Secretsを登録する

利用者本人が以下を登録します。

| Secret名 | 用途 |
|---|---|
| `THREADS_ACCESS_TOKEN` | Threads長期アクセストークン |
| `THREADS_USER_ID` | ThreadsユーザーID |
| `ASSETS_REPO_TOKEN` | Public画像リポジトリへの書き込み用。画像投稿を使う場合のみ |

Secretsの値を、運営者、チャット、メール、フォームへ送信しないでください。

## 4. Developer所有者と投稿アカウントが異なる場合

Meta Developerアプリの所有者と、実際にThreadsへ投稿するアカウントが異なる場合は、次のように分けます。

- アカウントA：Meta Developerアプリの所有者
- アカウントB：実際にThreadsへ投稿するアカウント

事前に、アカウントBが対象アプリのThreadsテスター招待を承認していることを確認します。

### 確認済みのトークン生成手順

1. 新しいシークレットウィンドウを開く
2. そのシークレットセッション内で、Meta for DevelopersへアカウントAとしてログインする
3. 対象アプリのThreads API設定を開く
4. アカウントB用のアクセストークン生成を開始する
5. 同じシークレットセッション内に表示されるThreads認証を、アカウントBとして完了する
6. 短期アクセストークンを長期アクセストークンへ交換する
7. 利用者本人が長期アクセストークンを`THREADS_ACCESS_TOKEN`へ登録する
8. 利用者本人がThreadsユーザーIDを`THREADS_USER_ID`へ登録する

パスワード、アクセストークン、認証コードは、運営者やAIへ送信しないでください。

アカウントAの通常ブラウザセッションからアカウントB向け認証を開始すると、Bが招待を承認済みでも次のエラーになる場合があります。

```text
Invalid Request: The user has not accepted the invite to test the app.
error_code=1349245
```

この場合は、エラー画面を再読み込みせず、Bの招待承認状態を確認したうえで、上記の新しいシークレットセッションからトークン生成をやり直します。

Metaの画面名や認証仕様は変更される可能性があるため、画面が異なる場合は最新の公式案内を確認してください。

## 5. 画像付き投稿を利用する場合

顧客本人のGitHubアカウントに、Public画像リポジトリを作ります。

推奨名：

```text
threads-autopilot-assets
```

Public画像リポジトリへ登録した画像は、インターネット上から閲覧できます。

以下は登録しないでください。

- 個人情報を含む画像
- 機密情報を含む画像
- 公開前に第三者へ見られて困る画像
- 利用権利を持たない画像
- 投稿本文、投稿予定、投稿履歴
- Secretsやトークン

## 6. 画像用Fine-grained Personal Access Token

画像投稿を利用する場合、利用者本人が画像リポジトリだけを対象にしたFine-grained Personal Access Tokenを作成します。

推奨権限：

- Repository access：画像用リポジトリ1つだけ
- Contents：Read and write
- 有効期限：必要な期間のみ

作成した値は、Private自動投稿リポジトリの`ASSETS_REPO_TOKEN`へ登録します。

## 7. 投稿データを登録する

投稿予定は`posts/schedules/`内のYAMLファイルへ登録します。

詳しい形式は`docs/POST_SCHEMA.md`を参照してください。

## 8. テスト順序

1. Threadsプロフィール取得テスト
2. テキスト投稿のdry run
3. 短いテキストのテスト投稿
4. 投稿履歴への記録確認
5. 画像変換のdry run
6. Public画像URLの表示確認
7. 画像付きテスト投稿
8. 2件のツリー投稿テスト
9. 二重投稿防止の確認
10. エラー時のIssue・ログ確認

## 9. 本番開始条件

以下をすべて確認してから本番運用を開始します。

- Secretsがコードやログに表示されない
- dry runが成功する
- テキスト投稿が成功する
- 投稿IDと投稿時刻が履歴に残る
- 画像URLが外部から参照できる
- ツリー投稿の順番が正しい
- 再実行しても二重投稿されない
- 失敗時に`status: error`と原因が記録される
