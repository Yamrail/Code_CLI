# YamRail/Code_CLI 引継ぎ票

R007/R008に基づくPrivate提出候補です。元のYamRail部材と今回のCLI、アダプタ、
配布・検査差分は、出典台帳と各ファイルのMANIFESTに分けて記録しています。
動作確認はローカルの実行証憑であり、本番認証やHuman承認ではありません。

まず `START_HERE.md`、`INSTALL.md`、`REPRODUCTION.md` を読み、次を実行してください。

```text
python yr_code.py evidence verify --manifest MANIFEST.json
python install.py
.\yr-code.cmd doctor --format json
.\yr-code.cmd demo
.\yr-code.cmd recon local --root fixtures/safe_public_or_synthetic
.\yr-code.cmd graph render --input fixtures/osint_case.json --type content --paper a4-landscape --out out/graph
.\yr-code.cmd report make --input fixtures/osint_case.json --paper a4-landscape --out out/report
.\yr-code.cmd status --format json
```

Linuxでは `python3` と `./yr-code.sh` を使用します。初回起動の原証憑、実行範囲と
限界は `evidence/observed_and_labelled/FIRST_BOOT_SUMMARY.json` に対応付けています。
既存の実行先を上書き・再試行せず、毎回新しい出力先を使用してください。

`hackathon_judge` は起動に必要な共通実装、OSS依存、合成Fixture、出典・検査票、
動画・スライドを含みます。`full_authorized_handoff` はこれに照査済みの追加ソース
を加えます。追加部材の参照先は `full_authorized_sources/SOURCE_INDEX.json` です。
工具候補の列挙、原ソースの梱包、インストール、実行許可を混同しません。
どちらも現時点ではPrivate候補であり、外部への開示許可を含みません。

Native WorkLedgerを状態の書込口として使います。レポート、Graph、状態表示、
Meterless World Modelは読取投影です。停止・復元時に結果不明となった外部効果を
自動再試行しません。既存Journalを別パスに移して現行状態へ再結合することも
ありません。`work_handover --run <実行ディレクトリ>` で証憑を引き継ぎ、
次の作業者は別の新規作業指示で開始してください。

Nightshift/NVIDIA NemotronとZetarisの実接続は未実行です。Meterlessのローカル
実装と合成経路は、実API接続の成績ではありません。大会のスポンサー必須条件は
未充足です。AutoCADは実ライセンスとユーザー端末の対話Brokerが未確認のため
起動しません。サーバー・Cloud・遠隔Workerからの実行には切り替えません。
Office/CAD/build工具の不足、RAM・暗号化・完全な隔離の未証明もHOLDに残します。

公開、応募、Privateソース開示、新規従量課金、正本昇格・mergeは、別のHuman判断票
が必要です。`HUMAN_SUBMISSION_GATE.json` はその未受領状態を記録します。
この引継ぎ票は、承認待ちを理由としたローカル検査の停止を指示するものではありません。
