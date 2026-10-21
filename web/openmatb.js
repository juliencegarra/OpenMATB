// Copyright 2023-2026, by Julien Cegarra & Benoît Valéry. All rights reserved.
// Institut National Universitaire Champollion (Albi, France).
// License : CeCILL, version 2.1 (see the LICENSE file)

// Browser launcher: loads Pyodide + pyglet in the background while the start menu
// is displayed, then runs main.py once the user clicks "Start" (a user gesture is
// required to enable audio and fullscreen).

import { installPygletEmscripten } from "./pyglet_emscripten.js";
import {
    SessionOutput, checkDataPipe, downloadText, gunzipIfNeeded, loadJatos, readConfigValue, sessionOutputSettings,
    sessionRelativePath,
} from "./session_output.js";
import { connectScorm } from "./scorm.js";
import { Cmi5Session, cmi5LaunchParameters, preferredLanguage } from "./cmi5.js";
import { SerialTrigger, describePort } from "./serial_trigger.js";
import { LslBridge } from "./lsl_bridge.js";

// Set by web/build.py: pyodide.mjs on the Pyodide CDN, or its copy shipped with the page (--pyodide local)
const PYODIDE_MODULE = new URL(document.querySelector('meta[name="pyodide-module"]').content, location.href).href;
const APP_DIR = "/app";
const SESSIONS_DIR = "/data/openmatb/sessions"; // pyglet.storage.get("openmatb").data / "sessions"
let storage = null; // pyglet's storage bridge (persists /data in IndexedDB), set by boot()
const FONT_FAMILY = "Noto Sans"; // core.platform.WEB_FONT_NAME, files downloaded by web/build.py
const FONT_WEIGHTS = [400, 700];

const $ = (id) => document.getElementById(id);

// Languages written from right to left (core.bidi.RTL_LANGUAGES): the start page is mirrored
const RTL_LANGUAGES = ["ar", "fa", "he", "ur", "yi"];

// Start page texts (OpenMATB itself is translated with gettext, see locales/)
const TEXTS = {
    en_EN: {
        language: "Language",
        mode: "Mode",
        run_scenario: "Run a scenario",
        replay_session: "Replay a session",
        choose_next: "The scenario (or session) is chosen in the next screen.",
        import_session: "Import a session file (optional)",
        sessions_kept: "Sessions run in this browser are kept and listed automatically.",
        fullscreen: "Fullscreen",
        start: "Start",
        session_ended: "Session ended",
        log_file: "The log file",
        kept_in_browser: "It is also kept in this browser for replay.",
        sending: "Sending…",
        ending_study: "End of the study…",
        study_not_ended: "The study could not be ended in JATOS:",
        sent_download: "Downloaded on this computer",
        sent_fallback: "Downloaded on this computer, because it could not be sent",
        sent_webdav: "Sent to the server (WebDAV)",
        sent_jatos: "Sent to JATOS",
        sent_datapipe: "Sent to DataPipe",
        sent_scorm: "Activity completed in the learning platform (LMS)",
        sent_cmi5: "Activity completed in the learning platform (LMS)",
        sent_cmi5_not_recorded: "Not recorded as completed: the learning platform (LMS) opened the activity in "
            + "browse or review mode",
        back_to_course: "Back to the course…",
        sent_none: "Not sent anywhere (web_session_output=none)",
        demo_not_recorded: "This was a demo: the session was not recorded.",
        restart_demo: "Restart the demo",
        not_sent: "Not sent to {destination}:",
        config_error: "Configuration error (config.ini):",
        stored_sessions: "Sessions kept in this browser",
        no_session: "No session yet.",
        download: "Download",
        delete: "Delete",
        delete_all: "Delete all the sessions",
        confirm_delete: "Delete the session {name} from this browser?",
        confirm_delete_all: "Delete the {count} sessions kept in this browser?",
        back_to_menu: "Back to menu",
        joystick_hint: "Joystick: press one of its buttons to detect it.",
        joystick_detected: "Joystick detected:",
        loading_python: "Loading Python…",
        loading_pyglet: "Loading pyglet…",
        loading_openmatb: "Loading OpenMATB…",
        ready: "Ready",
        loading_failed: "Loading failed:",
        browser_warn: "The Firefox browser cannot guarantee the timing accuracy of the results, "
            + "prefer Chrome or Edge.",
        browser_block: "This experiment requires Chrome or Edge: Firefox pauses for 0.1 to 1 s every few seconds, "
            + "which makes timing unreliable.",
        wasm_mime: "Slow loading",
        wasm_mime_detail: "The server does not send the .wasm files as application/wasm "
            + "(Moodle: Site administration > Server > File types).",
        trigger_box: "Trigger box (parallelport plugin)",
        no_port: "No port chosen.",
        choose_port: "Choose the port",
        serial_unsupported: "web_serial_trigger: this browser cannot use serial ports (use Chrome or Edge)",
        choose_port_first: "Choose the port of the trigger box",
        port_not_opened: "The port of the trigger box cannot be opened:",
        sent_trigger: "Trigger box: {count} values written",
        failed_trigger: "Trigger box: {count} values not written:",
        sent_lsl: "LSL bridge: {count} markers sent",
        failed_lsl: "LSL bridge: {count} markers not sent (bridge disconnected)",
    },
    fr_FR: {
        language: "Langue",
        mode: "Mode",
        run_scenario: "Lancer un scénario",
        replay_session: "Rejouer une session",
        choose_next: "Le scénario (ou la session) est choisi à l'écran suivant.",
        import_session: "Importer un fichier de session (facultatif)",
        sessions_kept: "Les sessions lancées dans ce navigateur sont conservées et listées automatiquement.",
        fullscreen: "Plein écran",
        start: "Démarrer",
        session_ended: "Session terminée",
        log_file: "Le fichier de log",
        kept_in_browser: "Il est aussi conservé dans ce navigateur pour le rejouer.",
        sending: "Envoi en cours…",
        ending_study: "Fin de l'étude…",
        study_not_ended: "L'étude n'a pas pu être terminée dans JATOS :",
        sent_download: "Téléchargé sur cet ordinateur",
        sent_fallback: "Téléchargé sur cet ordinateur, car il n'a pas pu être envoyé",
        sent_webdav: "Envoyé au serveur (WebDAV)",
        sent_jatos: "Envoyé à JATOS",
        sent_datapipe: "Envoyé à DataPipe",
        sent_scorm: "Activité terminée dans la plateforme de formation (LMS)",
        sent_cmi5: "Activité terminée dans la plateforme de formation (LMS)",
        sent_cmi5_not_recorded: "Non enregistrée comme terminée : la plateforme de formation (LMS) a ouvert "
            + "l'activité en mode consultation ou révision",
        back_to_course: "Retour au cours…",
        sent_none: "Envoyé nulle part (web_session_output=none)",
        demo_not_recorded: "C'était une démonstration : la session n'a pas été enregistrée.",
        restart_demo: "Relancer la démo",
        not_sent: "Non envoyé à {destination} :",
        config_error: "Erreur de configuration (config.ini) :",
        stored_sessions: "Sessions conservées dans ce navigateur",
        no_session: "Aucune session pour le moment.",
        download: "Télécharger",
        delete: "Supprimer",
        delete_all: "Supprimer toutes les sessions",
        confirm_delete: "Supprimer la session {name} de ce navigateur ?",
        confirm_delete_all: "Supprimer les {count} sessions conservées dans ce navigateur ?",
        back_to_menu: "Retour au menu",
        joystick_hint: "Joystick : appuyez sur l'un de ses boutons pour le détecter.",
        joystick_detected: "Joystick détecté :",
        loading_python: "Chargement de Python…",
        loading_pyglet: "Chargement de pyglet…",
        loading_openmatb: "Chargement d'OpenMATB…",
        ready: "Prêt",
        loading_failed: "Échec du chargement :",
        browser_warn: "Le navigateur Firefox ne peut garantir la précision temporelle des résultats, "
            + "privilégiez Chrome ou Edge.",
        browser_block: "Cette expérience nécessite Chrome ou Edge : Firefox s'interrompt 0,1 à 1 s toutes les "
            + "quelques secondes, ce qui rend la mesure du temps peu fiable.",
        wasm_mime: "Chargement lent",
        wasm_mime_detail: "Le serveur n'envoie pas les fichiers .wasm en application/wasm "
            + "(Moodle : Administration du site > Serveur > Types de fichiers).",
        trigger_box: "Boîtier de triggers (plugin parallelport)",
        no_port: "Aucun port choisi.",
        choose_port: "Choisir le port",
        serial_unsupported: "web_serial_trigger : ce navigateur ne peut pas utiliser les ports série "
            + "(utilisez Chrome ou Edge)",
        choose_port_first: "Choisissez le port du boîtier de triggers",
        port_not_opened: "Le port du boîtier de triggers ne peut pas être ouvert :",
        sent_trigger: "Boîtier de triggers : {count} valeurs écrites",
        failed_trigger: "Boîtier de triggers : {count} valeurs non écrites :",
        sent_lsl: "Pont LSL : {count} marqueurs envoyés",
        failed_lsl: "Pont LSL : {count} marqueurs non envoyés (pont déconnecté)",
    },
    de_DE: {
        language: "Sprache",
        mode: "Modus",
        run_scenario: "Ein Szenario starten",
        replay_session: "Eine Sitzung wiedergeben",
        choose_next: "Das Szenario (oder die Sitzung) wird im nächsten Bildschirm gewählt.",
        import_session: "Eine Sitzungsdatei importieren (optional)",
        sessions_kept: "Die in diesem Browser durchgeführten Sitzungen werden gespeichert und automatisch aufgelistet.",
        fullscreen: "Vollbild",
        start: "Starten",
        session_ended: "Sitzung beendet",
        log_file: "Die Logdatei",
        kept_in_browser: "Sie wird auch in diesem Browser für die Wiedergabe gespeichert.",
        sending: "Wird gesendet…",
        ending_study: "Ende der Studie…",
        study_not_ended: "Die Studie konnte in JATOS nicht beendet werden:",
        sent_download: "Auf diesen Computer heruntergeladen",
        sent_fallback: "Auf diesen Computer heruntergeladen, da sie nicht gesendet werden konnte",
        sent_webdav: "An den Server gesendet (WebDAV)",
        sent_jatos: "An JATOS gesendet",
        sent_datapipe: "An DataPipe gesendet",
        sent_scorm: "Aktivität in der Lernplattform (LMS) abgeschlossen",
        sent_cmi5: "Aktivität in der Lernplattform (LMS) abgeschlossen",
        sent_cmi5_not_recorded: "Nicht als abgeschlossen erfasst: Die Lernplattform (LMS) hat die Aktivität im "
            + "Ansichts- oder Überprüfungsmodus geöffnet",
        back_to_course: "Zurück zum Kurs…",
        sent_none: "Nirgendwohin gesendet (web_session_output=none)",
        demo_not_recorded: "Dies war eine Demo: Die Sitzung wurde nicht gespeichert.",
        restart_demo: "Demo neu starten",
        not_sent: "Nicht an {destination} gesendet:",
        config_error: "Konfigurationsfehler (config.ini):",
        stored_sessions: "In diesem Browser gespeicherte Sitzungen",
        no_session: "Noch keine Sitzung.",
        download: "Herunterladen",
        delete: "Löschen",
        delete_all: "Alle Sitzungen löschen",
        confirm_delete: "Die Sitzung {name} aus diesem Browser löschen?",
        confirm_delete_all: "Die {count} in diesem Browser gespeicherten Sitzungen löschen?",
        back_to_menu: "Zurück zum Menü",
        joystick_hint: "Joystick: Drücken Sie eine seiner Tasten, um ihn zu erkennen.",
        joystick_detected: "Joystick erkannt:",
        loading_python: "Python wird geladen…",
        loading_pyglet: "pyglet wird geladen…",
        loading_openmatb: "OpenMATB wird geladen…",
        ready: "Bereit",
        loading_failed: "Laden fehlgeschlagen:",
        browser_warn: "Der Browser Firefox kann die zeitliche Genauigkeit der Ergebnisse nicht garantieren, "
            + "verwenden Sie lieber Chrome oder Edge.",
        browser_block: "Dieses Experiment erfordert Chrome oder Edge: Firefox hält alle paar Sekunden für 0,1 bis "
            + "1 s an, wodurch die Zeitmessung unzuverlässig wird.",
        wasm_mime: "Langsames Laden",
        wasm_mime_detail: "Der Server sendet die .wasm-Dateien nicht als application/wasm "
            + "(Moodle: Website-Administration > Server > Dateitypen).",
        trigger_box: "Triggerbox (Plugin parallelport)",
        no_port: "Kein Port gewählt.",
        choose_port: "Port wählen",
        serial_unsupported: "web_serial_trigger: Dieser Browser kann keine seriellen Ports verwenden "
            + "(verwenden Sie Chrome oder Edge)",
        choose_port_first: "Wählen Sie den Port der Triggerbox",
        port_not_opened: "Der Port der Triggerbox kann nicht geöffnet werden:",
        sent_trigger: "Triggerbox: {count} Werte geschrieben",
        failed_trigger: "Triggerbox: {count} Werte nicht geschrieben:",
        sent_lsl: "LSL-Brücke: {count} Marker gesendet",
        failed_lsl: "LSL-Brücke: {count} Marker nicht gesendet (Brücke getrennt)",
    },
    es_ES: {
        language: "Idioma",
        mode: "Modo",
        run_scenario: "Ejecutar un escenario",
        replay_session: "Repetir una sesión",
        choose_next: "El escenario (o la sesión) se elige en la pantalla siguiente.",
        import_session: "Importar un archivo de sesión (opcional)",
        sessions_kept: "Las sesiones realizadas en este navegador se conservan y se listan automáticamente.",
        fullscreen: "Pantalla completa",
        start: "Comenzar",
        session_ended: "Sesión terminada",
        log_file: "El archivo de registro",
        kept_in_browser: "También se conserva en este navegador para repetirlo.",
        sending: "Enviando…",
        ending_study: "Fin del estudio…",
        study_not_ended: "No se pudo finalizar el estudio en JATOS:",
        sent_download: "Descargado en este ordenador",
        sent_fallback: "Descargado en este ordenador, porque no se pudo enviar",
        sent_webdav: "Enviado al servidor (WebDAV)",
        sent_jatos: "Enviado a JATOS",
        sent_datapipe: "Enviado a DataPipe",
        sent_scorm: "Actividad completada en la plataforma de aprendizaje (LMS)",
        sent_cmi5: "Actividad completada en la plataforma de aprendizaje (LMS)",
        sent_cmi5_not_recorded: "No registrada como completada: la plataforma de aprendizaje (LMS) abrió la "
            + "actividad en modo de consulta o de revisión",
        back_to_course: "Volver al curso…",
        sent_none: "No enviado a ningún sitio (web_session_output=none)",
        demo_not_recorded: "Era una demostración: la sesión no se ha guardado.",
        restart_demo: "Reiniciar la demostración",
        not_sent: "No enviado a {destination}:",
        config_error: "Error de configuración (config.ini):",
        stored_sessions: "Sesiones conservadas en este navegador",
        no_session: "Todavía no hay ninguna sesión.",
        download: "Descargar",
        delete: "Eliminar",
        delete_all: "Eliminar todas las sesiones",
        confirm_delete: "¿Eliminar la sesión {name} de este navegador?",
        confirm_delete_all: "¿Eliminar las {count} sesiones conservadas en este navegador?",
        back_to_menu: "Volver al menú",
        joystick_hint: "Joystick: pulse uno de sus botones para detectarlo.",
        joystick_detected: "Joystick detectado:",
        loading_python: "Cargando Python…",
        loading_pyglet: "Cargando pyglet…",
        loading_openmatb: "Cargando OpenMATB…",
        ready: "Listo",
        loading_failed: "Error de carga:",
        browser_warn: "El navegador Firefox no puede garantizar la precisión temporal de los resultados, "
            + "es preferible usar Chrome o Edge.",
        browser_block: "Este experimento requiere Chrome o Edge: Firefox se detiene de 0,1 a 1 s cada pocos "
            + "segundos, lo que hace que la medida del tiempo no sea fiable.",
        wasm_mime: "Carga lenta",
        wasm_mime_detail: "El servidor no envía los archivos .wasm como application/wasm "
            + "(Moodle: Administración del sitio > Servidor > Tipos de archivo).",
        trigger_box: "Caja de triggers (plugin parallelport)",
        no_port: "Ningún puerto elegido.",
        choose_port: "Elegir el puerto",
        serial_unsupported: "web_serial_trigger: este navegador no puede usar puertos serie "
            + "(use Chrome o Edge)",
        choose_port_first: "Elija el puerto de la caja de triggers",
        port_not_opened: "No se puede abrir el puerto de la caja de triggers:",
        sent_trigger: "Caja de triggers: {count} valores escritos",
        failed_trigger: "Caja de triggers: {count} valores no escritos:",
        sent_lsl: "Puente LSL: {count} marcadores enviados",
        failed_lsl: "Puente LSL: {count} marcadores no enviados (puente desconectado)",
    },
    it_IT: {
        language: "Lingua",
        mode: "Modalità",
        run_scenario: "Avvia uno scenario",
        replay_session: "Riproduci una sessione",
        choose_next: "Lo scenario (o la sessione) si sceglie nella schermata successiva.",
        import_session: "Importa un file di sessione (facoltativo)",
        sessions_kept: "Le sessioni svolte in questo browser sono conservate ed elencate automaticamente.",
        fullscreen: "Schermo intero",
        start: "Avvia",
        session_ended: "Sessione terminata",
        log_file: "Il file di log",
        kept_in_browser: "È anche conservato in questo browser per riprodurlo.",
        sending: "Invio in corso…",
        ending_study: "Fine dello studio…",
        study_not_ended: "Non è stato possibile terminare lo studio in JATOS:",
        sent_download: "Scaricato su questo computer",
        sent_fallback: "Scaricato su questo computer, perché non è stato possibile inviarlo",
        sent_webdav: "Inviato al server (WebDAV)",
        sent_jatos: "Inviato a JATOS",
        sent_datapipe: "Inviato a DataPipe",
        sent_scorm: "Attività completata nella piattaforma di apprendimento (LMS)",
        sent_cmi5: "Attività completata nella piattaforma di apprendimento (LMS)",
        sent_cmi5_not_recorded: "Non registrata come completata: la piattaforma di apprendimento (LMS) ha aperto "
            + "l'attività in modalità consultazione o revisione",
        back_to_course: "Torna al corso…",
        sent_none: "Non inviato da nessuna parte (web_session_output=none)",
        demo_not_recorded: "Era una dimostrazione: la sessione non è stata registrata.",
        restart_demo: "Riavvia la dimostrazione",
        not_sent: "Non inviato a {destination}:",
        config_error: "Errore di configurazione (config.ini):",
        stored_sessions: "Sessioni conservate in questo browser",
        no_session: "Ancora nessuna sessione.",
        download: "Scarica",
        delete: "Elimina",
        delete_all: "Elimina tutte le sessioni",
        confirm_delete: "Eliminare la sessione {name} da questo browser?",
        confirm_delete_all: "Eliminare le {count} sessioni conservate in questo browser?",
        back_to_menu: "Torna al menu",
        joystick_hint: "Joystick: premere uno dei suoi pulsanti per rilevarlo.",
        joystick_detected: "Joystick rilevato:",
        loading_python: "Caricamento di Python…",
        loading_pyglet: "Caricamento di pyglet…",
        loading_openmatb: "Caricamento di OpenMATB…",
        ready: "Pronto",
        loading_failed: "Caricamento non riuscito:",
        browser_warn: "Il browser Firefox non può garantire la precisione temporale dei risultati, "
            + "preferire Chrome o Edge.",
        browser_block: "Questo esperimento richiede Chrome o Edge: Firefox si interrompe da 0,1 a 1 s ogni pochi "
            + "secondi, il che rende inaffidabile la misura del tempo.",
        wasm_mime: "Caricamento lento",
        wasm_mime_detail: "Il server non invia i file .wasm come application/wasm "
            + "(Moodle: Amministrazione del sito > Server > Tipi di file).",
        trigger_box: "Trigger box (plugin parallelport)",
        no_port: "Nessuna porta scelta.",
        choose_port: "Scegli la porta",
        serial_unsupported: "web_serial_trigger: questo browser non può usare le porte seriali "
            + "(usare Chrome o Edge)",
        choose_port_first: "Scegliere la porta del trigger box",
        port_not_opened: "Impossibile aprire la porta del trigger box:",
        sent_trigger: "Trigger box: {count} valori scritti",
        failed_trigger: "Trigger box: {count} valori non scritti:",
        sent_lsl: "Ponte LSL: {count} marcatori inviati",
        failed_lsl: "Ponte LSL: {count} marcatori non inviati (ponte disconnesso)",
    },
    ja_JP: {
        language: "言語",
        mode: "モード",
        run_scenario: "シナリオを実行",
        replay_session: "セッションをリプレイ",
        choose_next: "シナリオ（またはセッション）は次の画面で選択します。",
        import_session: "セッションファイルを読み込む（任意）",
        sessions_kept: "このブラウザで実行したセッションは保存され、自動的に一覧表示されます。",
        fullscreen: "全画面",
        start: "開始",
        session_ended: "セッション終了",
        log_file: "ログファイル",
        kept_in_browser: "リプレイ用にこのブラウザにも保存されます。",
        sending: "送信中…",
        ending_study: "研究を終了しています…",
        study_not_ended: "JATOS で研究を終了できませんでした：",
        sent_download: "このコンピュータにダウンロードしました",
        sent_fallback: "送信できなかったため、このコンピュータにダウンロードしました",
        sent_webdav: "サーバーに送信しました (WebDAV)",
        sent_jatos: "JATOS に送信しました",
        sent_datapipe: "DataPipe に送信しました",
        sent_scorm: "学習プラットフォーム (LMS) でアクティビティを完了しました",
        sent_cmi5: "学習プラットフォーム (LMS) でアクティビティを完了しました",
        sent_cmi5_not_recorded: "完了として記録されていません：学習プラットフォーム (LMS) がアクティビティを"
            + "閲覧モードまたはレビューモードで開きました",
        back_to_course: "コースに戻る…",
        sent_none: "どこにも送信されていません (web_session_output=none)",
        demo_not_recorded: "これはデモでした：セッションは記録されていません。",
        restart_demo: "デモを再開",
        not_sent: "{destination} に送信されていません：",
        config_error: "設定エラー (config.ini)：",
        stored_sessions: "このブラウザに保存されたセッション",
        no_session: "まだセッションはありません。",
        download: "ダウンロード",
        delete: "削除",
        delete_all: "すべてのセッションを削除",
        confirm_delete: "セッション {name} をこのブラウザから削除しますか？",
        confirm_delete_all: "このブラウザに保存された {count} 件のセッションを削除しますか？",
        back_to_menu: "メニューに戻る",
        joystick_hint: "ジョイスティック：検出するにはいずれかのボタンを押してください。",
        joystick_detected: "ジョイスティックを検出しました：",
        loading_python: "Python を読み込み中…",
        loading_pyglet: "pyglet を読み込み中…",
        loading_openmatb: "OpenMATB を読み込み中…",
        ready: "準備完了",
        loading_failed: "読み込みに失敗しました：",
        browser_warn: "Firefox ブラウザでは結果の時間精度を保証できません。Chrome または Edge を使用してください。",
        browser_block: "この実験には Chrome または Edge が必要です：Firefox は数秒ごとに 0.1〜1 秒停止するため、"
            + "時間計測の信頼性が損なわれます。",
        wasm_mime: "読み込みが遅い",
        wasm_mime_detail: "サーバーが .wasm ファイルを application/wasm として送信していません"
            + "（Moodle：サイト管理 > サーバー > ファイルタイプ）。",
        trigger_box: "トリガーボックス（parallelport プラグイン）",
        no_port: "ポートが選択されていません。",
        choose_port: "ポートを選択",
        serial_unsupported: "web_serial_trigger：このブラウザではシリアルポートを使用できません（Chrome または Edge を使用してください）",
        choose_port_first: "トリガーボックスのポートを選択してください",
        port_not_opened: "トリガーボックスのポートを開けません：",
        sent_trigger: "トリガーボックス：{count} 個の値を書き込みました",
        failed_trigger: "トリガーボックス：{count} 個の値を書き込めませんでした：",
        sent_lsl: "LSL ブリッジ：{count} 個のマーカーを送信しました",
        failed_lsl: "LSL ブリッジ：{count} 個のマーカーを送信できませんでした（ブリッジ切断）",
    },
    zh_CN: {
        language: "语言",
        mode: "模式",
        run_scenario: "运行场景",
        replay_session: "回放会话",
        choose_next: "场景（或会话）将在下一个界面中选择。",
        import_session: "导入会话文件（可选）",
        sessions_kept: "在此浏览器中运行的会话会被保存并自动列出。",
        fullscreen: "全屏",
        start: "开始",
        session_ended: "会话已结束",
        log_file: "日志文件",
        kept_in_browser: "它也保存在此浏览器中，以便回放。",
        sending: "正在发送…",
        ending_study: "正在结束研究…",
        study_not_ended: "无法在 JATOS 中结束研究：",
        sent_download: "已下载到此计算机",
        sent_fallback: "由于无法发送，已下载到此计算机",
        sent_webdav: "已发送到服务器 (WebDAV)",
        sent_jatos: "已发送到 JATOS",
        sent_datapipe: "已发送到 DataPipe",
        sent_scorm: "已在学习平台 (LMS) 中完成活动",
        sent_cmi5: "已在学习平台 (LMS) 中完成活动",
        sent_cmi5_not_recorded: "未记录为已完成：学习平台 (LMS) 以浏览或复查模式打开了此活动",
        back_to_course: "返回课程…",
        sent_none: "未发送到任何地方 (web_session_output=none)",
        demo_not_recorded: "这是一次演示：会话未被记录。",
        restart_demo: "重新开始演示",
        not_sent: "未发送到 {destination}：",
        config_error: "配置错误 (config.ini)：",
        stored_sessions: "此浏览器中保存的会话",
        no_session: "暂无会话。",
        download: "下载",
        delete: "删除",
        delete_all: "删除所有会话",
        confirm_delete: "从此浏览器中删除会话 {name}？",
        confirm_delete_all: "删除此浏览器中保存的 {count} 个会话？",
        back_to_menu: "返回菜单",
        joystick_hint: "操纵杆：按下其任意按钮以进行检测。",
        joystick_detected: "已检测到操纵杆：",
        loading_python: "正在加载 Python…",
        loading_pyglet: "正在加载 pyglet…",
        loading_openmatb: "正在加载 OpenMATB…",
        ready: "就绪",
        loading_failed: "加载失败：",
        browser_warn: "Firefox 浏览器无法保证结果的时间精度，建议使用 Chrome 或 Edge。",
        browser_block: "本实验需要 Chrome 或 Edge：Firefox 每隔几秒会暂停 0.1 至 1 秒，导致计时不可靠。",
        wasm_mime: "加载缓慢",
        wasm_mime_detail: "服务器未以 application/wasm 类型发送 .wasm 文件"
            + "（Moodle：网站管理 > 服务器 > 文件类型）。",
        trigger_box: "触发盒（parallelport 插件）",
        no_port: "未选择端口。",
        choose_port: "选择端口",
        serial_unsupported: "web_serial_trigger：此浏览器无法使用串口（请使用 Chrome 或 Edge）",
        choose_port_first: "请选择触发盒的端口",
        port_not_opened: "无法打开触发盒的端口：",
        sent_trigger: "触发盒：已写入 {count} 个值",
        failed_trigger: "触发盒：{count} 个值未写入：",
        sent_lsl: "LSL 桥接：已发送 {count} 个标记",
        failed_lsl: "LSL 桥接：{count} 个标记未发送（桥接已断开）",
    },
    ar_SA: {
        language: "اللغة",
        mode: "الوضع",
        run_scenario: "تشغيل سيناريو",
        replay_session: "إعادة عرض جلسة",
        choose_next: "يتم اختيار السيناريو (أو الجلسة) في الشاشة التالية.",
        import_session: "استيراد ملف جلسة (اختياري)",
        sessions_kept: "يتم حفظ الجلسات التي تُجرى في هذا المتصفح وعرضها تلقائياً.",
        fullscreen: "ملء الشاشة",
        start: "ابدأ",
        session_ended: "انتهت الجلسة",
        log_file: "ملف السجل",
        kept_in_browser: "يتم حفظه أيضاً في هذا المتصفح لإعادة عرضه.",
        sending: "جارٍ الإرسال…",
        ending_study: "جارٍ إنهاء الدراسة…",
        study_not_ended: "تعذر إنهاء الدراسة في JATOS:",
        sent_download: "تم التنزيل على هذا الحاسوب",
        sent_fallback: "تم التنزيل على هذا الحاسوب لأنه تعذر إرساله",
        sent_webdav: "تم الإرسال إلى الخادم (WebDAV)",
        sent_jatos: "تم الإرسال إلى JATOS",
        sent_datapipe: "تم الإرسال إلى DataPipe",
        sent_scorm: "اكتمل النشاط في منصة التعلم (LMS)",
        sent_cmi5: "اكتمل النشاط في منصة التعلم (LMS)",
        sent_cmi5_not_recorded: "لم يُسجَّل كمكتمل: فتحت منصة التعلم (LMS) النشاط في وضع التصفح أو المراجعة",
        back_to_course: "العودة إلى المقرر…",
        sent_none: "لم يُرسل إلى أي مكان (web_session_output=none)",
        demo_not_recorded: "كان هذا عرضاً تجريبياً: لم يتم تسجيل الجلسة.",
        restart_demo: "إعادة تشغيل العرض التجريبي",
        not_sent: "لم يُرسل إلى {destination}:",
        config_error: "خطأ في الإعدادات (config.ini):",
        stored_sessions: "الجلسات المحفوظة في هذا المتصفح",
        no_session: "لا توجد جلسات بعد.",
        download: "تنزيل",
        delete: "حذف",
        delete_all: "حذف جميع الجلسات",
        confirm_delete: "حذف الجلسة {name} من هذا المتصفح؟",
        confirm_delete_all: "حذف الجلسات المحفوظة في هذا المتصفح ({count})؟",
        back_to_menu: "العودة إلى القائمة",
        joystick_hint: "عصا التحكم: اضغط على أحد أزرارها لاكتشافها.",
        joystick_detected: "تم اكتشاف عصا التحكم:",
        loading_python: "جارٍ تحميل Python…",
        loading_pyglet: "جارٍ تحميل pyglet…",
        loading_openmatb: "جارٍ تحميل OpenMATB…",
        ready: "جاهز",
        loading_failed: "فشل التحميل:",
        browser_warn: "لا يضمن متصفح Firefox دقة توقيت النتائج، يُفضَّل استخدام Chrome أو Edge.",
        browser_block: "تتطلب هذه التجربة Chrome أو Edge: يتوقف Firefox من 0.1 إلى 1 ثانية كل بضع ثوانٍ، "
            + "مما يجعل قياس الوقت غير موثوق.",
        wasm_mime: "تحميل بطيء",
        wasm_mime_detail: "لا يرسل الخادم ملفات .wasm بالنوع application/wasm "
            + "(Moodle: إدارة الموقع > الخادم > أنواع الملفات).",
        trigger_box: "صندوق المشغّلات (الإضافة parallelport)",
        no_port: "لم يتم اختيار منفذ.",
        choose_port: "اختر المنفذ",
        serial_unsupported: "web_serial_trigger: لا يستطيع هذا المتصفح استخدام المنافذ التسلسلية (استخدم Chrome أو Edge)",
        choose_port_first: "اختر منفذ صندوق المشغّلات",
        port_not_opened: "تعذر فتح منفذ صندوق المشغّلات:",
        sent_trigger: "صندوق المشغّلات: تمت كتابة {count} قيمة",
        failed_trigger: "صندوق المشغّلات: لم تتم كتابة {count} قيمة:",
        sent_lsl: "جسر LSL: تم إرسال {count} علامة",
        failed_lsl: "جسر LSL: لم يتم إرسال {count} علامة (الجسر غير متصل)",
    },
};

// ?lang= in the URL, otherwise the first browser language OpenMATB is translated in, otherwise English
function detectLanguage() {
    const requested = new URLSearchParams(location.search).get("lang");
    if (requested in TEXTS) {
        return requested;
    }
    for (const language of navigator.languages || [navigator.language]) {
        const code = String(language).toLowerCase().split("-")[0];
        const match = Object.keys(TEXTS).find((lang) => lang.toLowerCase().startsWith(code + "_"));
        if (match) {
            return match;
        }
    }
    return "en_EN";
}

const t = (key) => TEXTS[$("lang").value][key];

let statusKey = null;
const status = (key, detail = "") => {
    statusKey = key;
    $("pygletStatus").textContent = key ? `${t(key)} ${detail}`.trim() : detail;
};

function translatePage() {
    const lang = $("lang").value;
    document.documentElement.lang = lang.split("_")[0];
    document.documentElement.dir = RTL_LANGUAGES.includes(lang.split("_")[0]) ? "rtl" : "ltr";
    for (const element of document.querySelectorAll("[data-i18n]")) {
        element.textContent = TEXTS[lang][element.dataset.i18n];
    }
    for (const element of document.querySelectorAll("[data-i18n-title]")) {
        element.title = TEXTS[lang][element.dataset.i18nTitle];
    }
    if (statusKey) {
        status(statusKey);
    }
}

// ---- Psychophysiology: USB trigger box (parallelport plugin) and LSL bridge (labstreaminglayer plugin) ----
// Opened when a scenario starts, then used from Python (core/platform.py): window.openmatbSerialTrigger and
// window.openmatbLsl

const serialTrigger = SerialTrigger.supported() ? new SerialTrigger() : null;

function deviceSettings(configText) {
    return {
        serialTrigger: /^true$/i.test(readConfigValue(configText, "web_serial_trigger") || ""),
        baudRate: Number(readConfigValue(configText, "web_serial_baudrate")) || 115200,
        lslBridge: readConfigValue(configText, "web_lsl_bridge") || "",
    };
}

function showTriggerPort() {
    const label = $("trigger-port");
    if (serialTrigger?.port) {
        delete label.dataset.i18n;
        label.textContent = describePort(serialTrigger.port);
    } else {
        label.dataset.i18n = "no_port";
        label.textContent = t("no_port");
    }
}

// Once config.ini is loaded: the port of the trigger box (allowed in a previous visit). Returns the errors.
async function showDevices(configText) {
    const devices = deviceSettings(configText);
    $("trigger-options").hidden = !devices.serialTrigger;
    if (!devices.serialTrigger) {
        return [];
    }
    if (!serialTrigger) {
        return [t("serial_unsupported")];
    }
    await serialTrigger.restore().catch(console.warn);
    showTriggerPort();
    return [];
}

$("trigger-choose").addEventListener("click", async () => {
    try {
        await serialTrigger.choose(); // Needs the click
    } catch (error) {
        console.warn("[OpenMATB] No serial port chosen:", error);
    }
    showTriggerPort();
});

// When a scenario starts: returns the errors (the session must not start without its devices)
async function openDevices(devices) {
    const errors = [];
    if (devices.serialTrigger) {
        if (!serialTrigger) {
            errors.push(t("serial_unsupported"));
        } else if (!serialTrigger.port) {
            errors.push(t("choose_port_first"));
        } else {
            try {
                await serialTrigger.open(devices.baudRate);
                window.openmatbSerialTrigger = serialTrigger;
            } catch (error) {
                errors.push(`${t("port_not_opened")} ${error.message || error}`);
            }
        }
    }
    if (devices.lslBridge && !window.openmatbLsl) {
        const bridge = new LslBridge(devices.lslBridge);
        try {
            await bridge.connect();
            window.openmatbLsl = bridge;
        } catch (error) {
            errors.push(String(error.message || error));
        }
    }
    return errors;
}

// End of the session: the last trigger values and markers, for the end page
async function closeDevices() {
    const results = [];
    const trigger = window.openmatbSerialTrigger;
    if (trigger) {
        await trigger.close();
        const failed = trigger.errors.length;
        results.push({
            destination: "trigger",
            ok: !failed,
            text: failed
                ? `${t("failed_trigger").replace("{count}", failed)} ${trigger.errors[0]}`
                : t("sent_trigger").replace("{count}", trigger.written),
        });
    }
    const bridge = window.openmatbLsl;
    if (bridge) {
        bridge.close();
        const lost = bridge.queue.length;
        results.push({
            destination: "lsl",
            ok: !lost,
            text: t(lost ? "failed_lsl" : "sent_lsl").replace("{count}", lost || bridge.sent),
        });
    }
    return results;
}

// Browsers reveal a joystick only after one of its buttons is pressed (core/joystick.py reads it)
function showJoystick() {
    const gamepad = [...(navigator.getGamepads ? navigator.getGamepads() : [])].find((g) => g && g.connected);
    $("joystick-status").dataset.i18n = gamepad ? "joystick_detected" : "joystick_hint";
    $("joystick-status").textContent = t($("joystick-status").dataset.i18n);
    $("joystick-name").textContent = gamepad ? gamepad.id : "";
}
window.addEventListener("gamepadconnected", showJoystick);
window.addEventListener("gamepaddisconnected", showJoystick);

$("lang").value = detectLanguage();
translatePage();
$("lang").addEventListener("change", translatePage);
showJoystick();

// Browsers with known timing issues. Firefox pauses the page for 0.1 to 1 s every few seconds (garbage
// collection when the user is considered inactive, and others): measured by tests/web, see the README.
const TIMING_ISSUE_BROWSERS = [/Firefox\/|FxiOS\//];
const BROWSER_CHECK_MODES = ["warn", "block", "off"];

// ?browsercheck= in the URL, otherwise web_browser_check in config.ini (once OpenMATB is loaded), otherwise "warn"
function browserCheckMode(pyodide = null) {
    const requested = new URLSearchParams(location.search).get("browsercheck");
    if (BROWSER_CHECK_MODES.includes(requested)) {
        return requested;
    }
    try {
        const config = pyodide?.FS.readFile(`${APP_DIR}/config.ini`, { encoding: "utf8" }) ?? "";
        const mode = (config.match(/^\s*web_browser_check\s*=\s*(\w+)/m) || [])[1]?.toLowerCase();
        if (BROWSER_CHECK_MODES.includes(mode)) {
            return mode;
        }
    } catch (error) {
        console.warn("config.ini not readable:", error);
    }
    return "warn";
}

// Show (or hide) the notice for browsers with timing issues. Returns false when starting is not allowed.
// Called when the page opens, then again once config.ini is available (it is in app.zip).
function checkBrowser(pyodide = null) {
    const mode = browserCheckMode(pyodide);
    const concerned = mode !== "off" && TIMING_ISSUE_BROWSERS.some((pattern) => pattern.test(navigator.userAgent));
    $("browser-warning").hidden = !concerned;
    if (!concerned) {
        return true;
    }
    $("browser-warning").dataset.i18n = `browser_${mode}`;
    $("browser-warning").textContent = t(`browser_${mode}`);
    return mode !== "block";
}
checkBrowser();

// ?demo=1 (Demo tab of the website): runs the demo scenario, and nothing is recorded
const DEMO = new URLSearchParams(location.search).get("demo") === "1";
const DEMO_SCENARIO = "demo.txt";
// config.ini values of the demo: no session number to acknowledge, and the session is not sent anywhere
const DEMO_CONFIG = { display_session_number: "False", web_session_output: "none" };

function applyDemoConfig(pyodide) {
    let config = readAppConfig(pyodide);
    for (const [key, value] of Object.entries(DEMO_CONFIG)) {
        config = config.replace(new RegExp(`^(\\s*${key}\\s*=).*$`, "m"), `$1${value}`);
    }
    pyodide.FS.writeFile(`${APP_DIR}/config.ini`, config);
}
if (DEMO) {
    $("mode").value = "scenario";
    $("mode").hidden = true;
    document.querySelector('label[for="mode"]').hidden = true;
    $("back").dataset.i18n = "restart_demo";
    $("back").textContent = t("restart_demo");
}

// Run by an LMS (SCORM or cmi5 package): the LMS records the completion, participants only run the scenario
function runByLms() {
    $("mode").value = "scenario";
    $("mode").hidden = true;
    document.querySelector('label[for="mode"]').hidden = true;
    $("back").hidden = true; // The LMS takes over at the end
}

const scorm = connectScorm();
if (scorm) {
    runByLms();
    window.addEventListener("pagehide", () => scorm.terminate());
}

// Launched by a cmi5 LMS: xAPI statements sent to its LRS (initialized, completed, terminated). lmsErrors: the launch
// was refused (e.g. the page was reloaded: the LMS gives its token only once), the session must not start.
const cmi5Launch = cmi5LaunchParameters();
const cmi5 = cmi5Launch ? new Cmi5Session(cmi5Launch) : null;
const lmsErrors = [];
const cmi5Ready = (async () => {
    if (!cmi5) {
        return;
    }
    runByLms();
    try {
        await cmi5.initialize();
    } catch (error) {
        console.error(error);
        lmsErrors.push(String(error.message || error));
        return;
    }
    window.addEventListener("pagehide", () => cmi5.terminate({ keepalive: true }).catch(console.error));
    if (!new URLSearchParams(location.search).get("lang")) {
        const language = preferredLanguage(await cmi5.languagePreference(), Object.keys(TEXTS));
        if (language) {
            $("lang").value = language;
            translatePage();
        }
    }
})();

// cmi5: after the "terminated" statement, the LMS takes over (its return address, or it closes the window itself)
async function returnToCourse() {
    await cmi5.terminate().catch(console.error);
    if (cmi5.returnURL) {
        location.href = cmi5.returnURL;
    }
}

async function loadFonts() {
    // pyglet measures and renders text with the fonts known by the document. The Arabic and Hebrew fonts join the same
    // family for their characters (core.bidi draws Arabic with presentation forms, missing from some system fonts).
    // All are loaded now: pyglet keeps the glyphs it got, even from a fallback font
    const ranges = {
        "noto-sans": undefined,
        "noto-sans-arabic": "U+0600-06FF, U+0750-077F, U+0870-08FF, U+FB50-FDFF, U+FE70-FEFF",
        "noto-sans-hebrew": "U+0590-05FF, U+FB1D-FB4F",
    };
    for (const [name, unicodeRange] of Object.entries(ranges)) {
        for (const weight of FONT_WEIGHTS) {
            const descriptors = unicodeRange ? { weight: String(weight), unicodeRange } : { weight: String(weight) };
            const face = new FontFace(FONT_FAMILY, `url(fonts/${name}-${weight}.woff2)`, descriptors);
            document.fonts.add(await face.load());
        }
    }
}

// Pyodide uses JSPI (WebAssembly.Suspending) when the browser has it, as Chrome and Edge do since version 137. On some
// Windows computers it makes the tab crash silently (STATUS_ACCESS_VIOLATION), a bug of Pyodide still open:
// https://github.com/pyodide/pyodide/issues/6106 (seen with Pyodide 0.28, not reproduced here). OpenMATB never waits
// for a JavaScript promise from synchronous Python code (run_sync), which is what JSPI is for: hide it from Pyodide.
// To remove when this issue is fixed.
function disableJspi() {
    delete WebAssembly.Suspending;
    delete WebAssembly.promising;
}

// LMSs (Moodle...) serve the .wasm files with a generic MIME type, which the streaming compilation refuses
// ("Incorrect response MIME type. Expected 'application/wasm'"): compile them from their bytes instead
function allowWasmWithoutMimeType() {
    for (const [streamingName, bytesName] of [["compileStreaming", "compile"], ["instantiateStreaming", "instantiate"]]) {
        const streaming = WebAssembly[streamingName];
        if (!streaming) {
            continue;
        }
        WebAssembly[streamingName] = async (source, ...args) => {
            const response = await source;
            const mimeType = response.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase();
            if (mimeType === "application/wasm") {
                return streaming.call(WebAssembly, response, ...args);
            }
            $("wasm-mime").hidden = false;
            return WebAssembly[bytesName](await response.arrayBuffer(), ...args);
        };
    }
}

// Options of loadPyodide. Pyodide shipped with the page (--pyodide local): its pyodide.asm.mjs module is renamed
// pyodide.asm.js (PYODIDE_FILES of web/build.py), which loadPyodide would not find: import it here and give it
async function pyodideOptions() {
    const options = { enableRunUntilComplete: false }; // It uses JSPI (see disableJspi)
    if (PYODIDE_MODULE.endsWith("/pyodide-module.js")) {
        const { default: createPyodideModule } = await import(new URL("pyodide.asm.js", PYODIDE_MODULE).href);
        options.createPyodideModule = createPyodideModule;
    }
    return options;
}

async function boot() {
    status("loading_python");
    allowWasmWithoutMimeType();
    disableJspi();
    await loadFonts();
    const { loadPyodide } = await import(PYODIDE_MODULE);
    const pyodide = await loadPyodide(await pyodideOptions());
    // Mounts /data (IndexedDB, where sessions are kept). The /cache mount (OPFS) is optional: Safari refuses
    // OPFS in private browsing, which made the loading fail. OpenMATB does not use it: keep /cache in memory then.
    const bridge = await installPygletEmscripten(pyodide, { cachePath: null });
    try {
        await bridge.mount_opfs("/cache");
    } catch (error) {
        console.warn("OPFS unavailable, /cache kept in memory:", error);
        pyodide.FS.mkdirTree("/cache");
    }

    status("loading_pyglet");
    await pyodide.loadPackage("micropip");
    const micropip = pyodide.pyimport("micropip");
    const wheels = (await (await fetch("wheels.txt")).text()).trim().split("\n");
    for (const wheel of wheels) {
        await micropip.install(new URL(`wheels/${wheel}`, location.href).href);
    }

    status("loading_openmatb");
    const app = await (await fetch("app.zip")).arrayBuffer();
    pyodide.unpackArchive(app, "zip", { extractDir: APP_DIR });
    if (DEMO) {
        applyDemoConfig(pyodide);
    }
    pyodide.runPython(`import os, sys; os.chdir("${APP_DIR}"); sys.path.insert(0, "${APP_DIR}")`);

    window.openmatb = { pyodide }; // for debugging from the browser console
    storage = bridge;
    status("ready");
    await cmi5Ready;
    const outputErrors = sessionOutputSettings(readAppConfig(pyodide)).errors;
    const deviceErrors = DEMO ? [] : await showDevices(readAppConfig(pyodide));
    const errors = [...lmsErrors, ...outputErrors, ...deviceErrors];
    $("start").disabled = !checkBrowser(pyodide) || !showConfigErrors(errors);
    return pyodide;
}

function readAppConfig(pyodide) {
    try {
        return pyodide.FS.readFile(`${APP_DIR}/config.ini`, { encoding: "utf8" });
    } catch {
        return "";
    }
}

// Show the configuration errors (session destinations) on the start page. Returns false if there are some.
function showConfigErrors(errors) {
    $("config-error").hidden = errors.length === 0;
    $("config-error").textContent = errors.length ? `${t("config_error")} ${errors.join(" ; ")}` : "";
    return errors.length === 0;
}

// Session file destinations (web_session_output in config.ini), set when a scenario is started
let sessionOutput = null;
const DESTINATION_NAMES = {
    download: "download", webdav: "WebDAV", jatos: "JATOS", datapipe: "DataPipe", scorm: "LMS", cmi5: "LMS",
};

async function importSession(pyodide, file, bytes) {
    // Imported CSV files are stored with the browser sessions, so they appear in the replay selector.
    // Compressed files (.csv.gz, as sent to JATOS) are stored decompressed.
    const folder = `${SESSIONS_DIR}/imported`;
    pyodide.FS.mkdirTree(folder);
    const csv = await gunzipIfNeeded(bytes);
    pyodide.FS.writeFile(`${folder}/${file.name.replace(/\.gz$/i, "")}`, new Uint8Array(csv));
}

const ready = boot().catch((error) => {
    status("loading_failed", String(error));
    throw error;
});

// OpenMATB uses function keys (F1-F6 in sysmon...): don't let the browser reload the page,
// open its help or move the focus. preventDefault() still lets pyglet receive the key.
window.addEventListener("keydown", (event) => {
    if (!$("pygletCanvas").hidden && /^F([1-9]|1[0-2])$/.test(event.key) && event.key !== "F11") {
        event.preventDefault();
    }
}, { capture: true });

// ---- Sessions kept in this browser (replay mode): download them again or delete them ----

// Session files under SESSIONS_DIR (run in this browser, or imported), the most recent first
function storedSessions(pyodide) {
    const sessions = [];
    const walk = (folder) => {
        let names;
        try {
            names = pyodide.FS.readdir(folder);
        } catch {
            return; // No session yet
        }
        for (const name of names.filter((n) => n !== "." && n !== "..")) {
            const path = `${folder}/${name}`;
            const stat = pyodide.FS.stat(path);
            if (pyodide.FS.isDir(stat.mode)) {
                walk(path);
            } else if (name.endsWith(".csv")) {
                const time = new Date(stat.mtime).getTime();
                sessions.push({ path, name, folder: folder.slice(SESSIONS_DIR.length + 1), size: stat.size, time });
            }
        }
    };
    walk(SESSIONS_DIR);
    return sessions.sort((a, b) => b.time - a.time);
}

function sessionButton(label, icon, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "icon";
    button.title = label;
    button.setAttribute("aria-label", label);
    button.textContent = icon;
    button.addEventListener("click", action);
    return button;
}

async function deleteSessions(pyodide, sessions) {
    for (const session of sessions) {
        pyodide.FS.unlink(session.path);
    }
    await storage.sync_idbfs(); // Also delete them from the browser storage
    showStoredSessions();
}

async function showStoredSessions() {
    if ($("mode").value !== "replay") {
        return;
    }
    const pyodide = await ready;
    const sessions = storedSessions(pyodide);
    $("sessions-empty").hidden = sessions.length > 0;
    $("delete-all").hidden = sessions.length === 0;
    $("sessions-list").replaceChildren(...sessions.map((session) => {
        const row = document.createElement("li");
        const label = document.createElement("span");
        label.className = "session-name";
        label.textContent = session.name;
        const details = document.createElement("small");
        const size = `${Math.max(1, Math.round(session.size / 1024))} kB`;
        details.textContent = session.folder ? `${session.folder} · ${size}` : size;
        label.append(details);
        row.append(
            label,
            sessionButton(t("download"), "⬇️", () => {
                downloadText(session.name, pyodide.FS.readFile(session.path, { encoding: "utf8" }));
            }),
            sessionButton(t("delete"), "🗑️", () => {
                if (window.confirm(t("confirm_delete").replace("{name}", session.name))) {
                    deleteSessions(pyodide, [session]);
                }
            }),
        );
        return row;
    }));
    $("delete-all").onclick = () => {
        if (window.confirm(t("confirm_delete_all").replace("{count}", sessions.length))) {
            deleteSessions(pyodide, sessions);
        }
    };
}

$("mode").addEventListener("change", () => {
    $("replay-options").hidden = $("mode").value !== "replay";
    showStoredSessions();
});

$("start").addEventListener("click", async () => {
    // Once: a second click during the awaits below ran main.py twice (two schedulers, every row logged twice)
    if ($("start").disabled) {
        return;
    }
    $("start").disabled = true;
    // Everything that needs the user gesture must happen before the first await
    const wantsFullscreen = $("fullscreen").checked;
    const fullscreen = wantsFullscreen ? document.documentElement.requestFullscreen().catch(() => {}) : null;

    const params = new URLSearchParams(location.search);
    params.set("lang", $("lang").value);
    params.set("mode", $("mode").value);
    if (DEMO && !params.has("scenario")) {
        params.set("scenario", DEMO_SCENARIO);
    }
    history.replaceState(null, "", `?${params}`);

    const file = $("mode").value === "replay" ? $("session-file").files[0] : undefined;
    const bytes = file ? await file.arrayBuffer() : null;
    const pyodide = await ready;

    // Where the session file will go. config.ini is read again: it may have been changed since the loading
    if ($("mode").value !== "replay") {
        const settings = sessionOutputSettings(readAppConfig(pyodide));
        settings.errors.unshift(...lmsErrors);
        let jatos;
        try {
            if (settings.destinations.includes("jatos")) {
                jatos = await loadJatos();
            }
        } catch (error) {
            settings.errors.push(String(error.message || error));
        }
        // Better now than after the session: DataPipe must accept the files of the experiment (the demo sends nothing)
        if (settings.destinations.includes("datapipe") && !settings.errors.length && !DEMO) {
            try {
                await checkDataPipe(settings.datapipeExperiment);
            } catch (error) {
                settings.errors.push(String(error.message || error));
            }
        }
        // Last: the trigger box and the LSL bridge are opened only if the session can start
        if (!settings.errors.length && !DEMO) {
            await showDevices(readAppConfig(pyodide)); // The port may have to be chosen
            settings.errors.push(...await openDevices(deviceSettings(readAppConfig(pyodide))));
        }
        if (!showConfigErrors(settings.errors)) {
            if (document.fullscreenElement) {
                document.exitFullscreen();
            }
            $("start").disabled = false;
            return;
        }
        sessionOutput = new SessionOutput(settings, { jatos });
    }

    $("menu").hidden = true;
    $("pygletCanvas").hidden = false;
    await fullscreen;

    if (file) {
        await importSession(pyodide, file, bytes);
    }
    status(null);
    try {
        await pyodide.runPythonAsync(`import runpy; runpy.run_path("main.py", run_name="__main__")`);
        $("pygletCanvas").focus();
    } catch (error) {
        status(null, String(error));
        console.error(error);
    }
});

// Back to the menu, keeping the chosen language
const backToMenu = () => {
    location.href = `${location.pathname}?lang=${$("lang").value}${DEMO ? "&demo=1" : ""}`;
};
$("back").addEventListener("click", backToMenu);

// Dispatched when OpenMATB closes (end of scenario, replay closed or selection cancelled)
document.addEventListener("openmatb-exit", () => {
    if ($("end").hidden) {
        // cmi5: reloading the page would fail (the LMS gives its token only once)
        cmi5 ? returnToCourse() : backToMenu();
    }
});

const readSessionFile = (pyodide, path) => pyodide.FS.readFile(path, { encoding: "utf8" });

// Dispatched by core.logger.Logger.checkpoint() every 10 s: send the file written so far (if configured)
document.addEventListener("openmatb-checkpoint", async (event) => {
    if (sessionOutput) {
        const pyodide = await ready;
        sessionOutput.checkpoint(sessionRelativePath(event.detail), readSessionFile(pyodide, event.detail));
    }
});

function destinationItem(text, ok) {
    const item = document.createElement("li");
    item.className = ok === undefined ? "" : ok ? "ok" : "failed";
    item.textContent = text;
    return item;
}

// Dispatched by core.logger.Logger.end_session(), with the path of the session file: download it and/or send it
document.addEventListener("openmatb-end", async (event) => {
    if (document.fullscreenElement) {
        document.exitFullscreen();
    }
    $("pygletCanvas").hidden = true;
    const relativePath = sessionRelativePath(event.detail);
    $("end-file").textContent = relativePath.split("/").pop();
    $("end-destinations").replaceChildren(destinationItem(t("sending")));
    // JATOS (like an LMS) takes over at the end: going back to the menu would reload the page and leave the study
    // run unfinished
    const inJatos = Boolean(sessionOutput?.settings.destinations.includes("jatos"));
    $("back").hidden = inJatos || Boolean(scorm || cmi5);
    $("end").hidden = false;

    const pyodide = await ready;
    if (DEMO) {
        // Not kept for replay either
        pyodide.FS.unlink(event.detail);
        await storage.sync_idbfs();
        $("end-destinations").replaceChildren(destinationItem(t("demo_not_recorded")));
        document.querySelector('#end [data-i18n="kept_in_browser"]').hidden = true;
        return;
    }
    const output = sessionOutput || new SessionOutput(sessionOutputSettings(""));
    const results = await output.finish(relativePath, readSessionFile(pyodide, event.detail));
    results.push(...await closeDevices());
    if (scorm) {
        const ok = scorm.complete(relativePath);
        results.push(ok ? { destination: "scorm", ok } : { destination: "scorm", ok, error: "see the console" });
    }
    if (cmi5) {
        try {
            const recorded = await cmi5.complete(relativePath);
            results.push({ destination: recorded ? "cmi5" : "cmi5_not_recorded", ok: recorded || undefined });
        } catch (error) {
            console.error(error);
            results.push({ destination: "cmi5", ok: false, error: String(error.message || error) });
        }
    }
    const resultText = (result) => {
        if (result.text) {
            return result.text;
        }
        return result.ok !== false
            ? t(`sent_${result.destination}`)
            : `${t("not_sent").replace("{destination}", DESTINATION_NAMES[result.destination])} ${result.error}`;
    };
    $("end-destinations").replaceChildren(...results.map((result) => destinationItem(resultText(result), result.ok)));
    // JATOS: end the study run (JATOS end page, or the redirection set in JATOS, e.g. to Prolific)
    if (results.some((result) => result.destination === "jatos" && result.ok)) {
        $("end-destinations").append(destinationItem(t("ending_study")));
        await new Promise((resolve) => setTimeout(resolve, 1000)); // Time to read that the file was sent
        try {
            console.info("[OpenMATB] JATOS: ending the study run");
            await window.jatos.endStudy();
            return; // JATOS shows its end page
        } catch (error) {
            console.error("[OpenMATB] JATOS: the study run could not be ended:", error);
            $("end-destinations").lastChild.replaceWith(destinationItem(
                `${t("study_not_ended")} ${error?.message || error?.responseText || error}`, false,
            ));
        }
    }
    if (cmi5) {
        $("end-destinations").append(destinationItem(t("back_to_course")));
        await new Promise((resolve) => setTimeout(resolve, 1000)); // Time to read where the file went
        await returnToCourse();
        return;
    }
    $("back").hidden = Boolean(scorm); // JATOS did not take over
});
