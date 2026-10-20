# Claude監査の実行復旧記録

## 対象

Issue #4、商品PR #5、商品画像の基準commit `7dd35719f7966674788caf5b5f2e91455b219519`。画像24枚・main/tab・プレビュー・販売ZIPは既存のまま再利用する。保守変更は別PRとして分離する。

## 確認済み

- 直前成功run `39293713221` と失敗run `39296497285` は、Action SHA `5eb090f3c3afd701a0672cd32981197ca27688f6` とClaude Code `2.1.303` が同じ。
- 失敗は審査開始前、1ターン、0ドル、モデル利用なし。単に `subtype:success` でも `is_error:true` なら失敗。
- 既存workflowは失敗時の詳細を出さず、実行ファイルも保存しないため、原因を確定できなかった。
- 上流issue #1901 は類似例にすぎず、この環境での原因と断定しない。

## 修復

- 最初に同じリポジトリsecret・同じモデルで公式Messages APIへ1出力トークンの接続確認を1回だけ送る。自動再試行なし。鍵・生レスポンス・プロンプトを出力しない。
- エラーを認証、権限、残高、利用上限、モデル、レート制限、サービス障害に分類して安全なJSONとjob summaryに記録する。
- 事前確認失敗時は本審査を開始しない。Action失敗時も必ず診断し、安全なJSONだけ7日間保存する。
- 正常に接続できれば、修正済み24枚をまとめて1回審査する。合格条件は88点以上かつ重大欠陥9項目全PASSのまま。
- 課金経路、billing header、認証制限の迂回はしない。

## 検証

ローカル `python -m pytest -q tests/test_claude_diagnostics.py`: 6 passed。Pythonコンパイル、workflow YAML構文、事前確認→Action→常時診断の順序を確認済み。商品画像は変更していないため、既存CI成功run `39296402942` を引き継ぐ。新PRでもCIを実行する。

## 次の判断

1. 実際のGitHub実行結果とrequest-idを確認して原因を確定する。
2. 残高/利用上限/鍵等の本人操作が必要な場合のみ、具体的な画面と操作を伝える。
3. 接続可能なら独立審査の結果を確認し、88点・重大欠陥全PASSまで販売準備完了にしない。
4. 商品PR #5 はdraftを保ち、重複課金を防ぐ。通常の定期進捗報告は再開しない。

## 実測結果（2026-10-21 00:05 JST）

[診断run 39445121329](https://github.com/ayaharu227-lab/LINE-/actions/runs/39445121329) にて、Actionを起動する前の公式Messages API直接接続がHTTP 400 / `invalid_request_error` / `credit_balance_rejected` を返した。request-id: `req_011CgDhGc6qKXRx5DS73NB2q`。GitHub登録済みsecretを使った1回の呼び出しで確認。Action固有の不具合だけが原因という見立ては、この実測では支持できない。残高の実額やキーの所属組織名は、この権限では読めないため断定しない。

事前確認失敗により本審査は自動でスキップされ、安全な診断JSONがartifact `12275860710` へ保存された。APIキーや生の実行内容は出力していない。

[CI 39445121151](https://github.com/ayaharu227-lab/LINE-/actions/runs/39445121151) 成功。`validate_stickers.py`: 24枚＋main/tab PASS、pytest: **12 passed**。これでプログラム側の診断・不要な本審査起動防止は実機確認できたが、外部API接続自体は未復旧。独立商品審査の条件は未達のまま。

## 本人操作と再開条件

1. [Claude ConsoleのBilling](https://platform.claude.com/settings/billing) にログインし、GitHubの `ANTHROPIC_API_KEY` を作成した組織を選ぶ。
2. Settings > Billingで、その組織の利用可能な**購入済みクレジット**を確認する。不足時はBuy creditsで本人が追加する。残高が既にある場合は追加購入を重ねず、キーの所属組織と購入先を照合し、必要ならこのrequest-idを添えて本人からサポートへ相談する。秘密キーをチャットへ送る必要はない。
3. 公式案内ではMax/Teamに付属する月次APIクレジットはGitHub Action起動のClaude Codeには適用されない。表示残高だけで判断せず、購入済みか付属APIクレジットかも確認する。新契約や自動チャージ設定は行わない。
4. 本人から残高/組織の確認完了を受けた後、保守PR #7をreadyに戻して事前確認＋商品監査を1回実行する。課金状態が変わらない間は再実行しない。商品PR #5と保守PR #7はdraftのまま維持する。
5. 同じ商品画像の審査が88点以上・重大欠陥9項目全PASSになってから保守修正を統合し、商品PRの完了状態を整理する。本人のLINEログイン・規約同意・申請・振込先入力はその後の工程。

公式根拠: [API利用の支払い方法](https://support.claude.com/en/articles/8977456-how-do-i-pay-for-my-claude-api-usage)、[Max/Team付属APIクレジットの適用範囲](https://support.claude.com/en/articles/17154008-monthly-api-credits-for-max-and-team-plans)。

## 合否判定の修復（2026-10-21）

従来のworkflowは結果文にAPPROVE / REQUEST_CHANGES / BLOCKのいずれかが含まれれば正常終了しており、82点・要修正の監査でもworkflowが成功していた。合格状態として誤読しないよう、外部AIを追加実行せずに検証処理を分離して修復した。

- 現在のhead SHAに対応し、claude[bot]またはgithub-actions[bot]が投稿した先頭マーカー付きレビューだけを採用。古いcommit、一般ユーザーの同名マーカー、同一commitへの複数レビューは合格に使わない。
- 機械判定用JSONを監査プロンプトへ追加。配点7項目の整数範囲と合計、88点以上、重大欠陥9項目全PASS、24枚・main/tab・明暗プレビューの確認、末尾APPROVEの一致をすべて必須にする。
- 欠落、重複キー、矛盾、不正な数値、未確認画像、REQUEST_CHANGES / BLOCKは不合格。結果文中の単なるAPPROVEという単語では通さない。
- Claudeが投稿後に短い完了文だけ返しても、PRに投稿された完全なレビューをページ送りで取得して評価する。投稿済みなら重複投稿しない。
- 合否JSONを成否にかかわらず安全な診断JSONと一緒に保存する。画像や審査の判断基準自体は変更していない。

ローカル: 診断6件＋合否判定17件＝**23件PASS**。Pythonコンパイル、YAML、合否判定後に証拠保存される順序もPASS。追加のAPI/Claude呼び出しは0回。リポジトリCIでは既存の商品検査6件と合わせて29件を確認する。

次の着手先は本人の残高/組織確認後の1回の最終監査。合格前に画像変更、商品PR統合、LINE申請は行わない。本人確認待ちで進められる独立修正がなくなった場合は定期実行を一時停止し、本人の確認完了後に既存設定で再開する。停止は商品完成の意味ではない。
