// Admin PDF Toolkit — Windows launcher (AdminPDFToolkit.exe).
//
// A small WinForms front end for the self-contained package: it checks
// every component one by one (python -m adminpdf.selfcheck), starts the
// server without any console window, offers signed updates (python -m
// adminpdf.updater) and can hide in the notification area.
//
// Written for C# 5 so the csc.exe that ships with .NET Framework 4.x on
// every Windows 10/11 PC can build it — no SDK, packer or third-party code.

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;
using System.Windows.Forms;

namespace AdminPdfToolkit
{
    static class Program
    {
        [STAThread]
        static int Main()
        {
            bool created;
            using (var mutex = new Mutex(true, "Local\\AdminPDFToolkitLauncher", out created))
            {
                if (!created)
                {
                    // Already running (perhaps hidden in the tray): just open the app.
                    Launcher.OpenUrl(Launcher.AppUrl());
                    return 0;
                }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                Application.Run(new LauncherForm());
                GC.KeepAlive(mutex);
            }
            return 0;
        }
    }

    static class Launcher
    {
        public static readonly string Root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        public static readonly string DataDir = Path.Combine(Root, "data");
        // APT_LAUNCHER_PYTHON: development override (e.g. a source checkout's venv).
        public static readonly string PythonExe =
            Environment.GetEnvironmentVariable("APT_LAUNCHER_PYTHON") ?? Path.Combine(Root, "python\\python.exe");
        public static readonly bool Tr = CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "tr";

        public static string T(string tr, string en) { return Tr ? tr : en; }

        public static int Port()
        {
            int port;
            return int.TryParse(Environment.GetEnvironmentVariable("APT_PORT"), out port) ? port : 8000;
        }

        public static string AppUrl() { return "https://localhost:" + Port() + "/"; }

        public static void OpenUrl(string url)
        {
            try { Process.Start(new ProcessStartInfo(url) { UseShellExecute = true }); }
            catch (Exception) { }
        }

        /// <summary>python.exe with the package's environment, never a console window.</summary>
        public static Process StartPython(string arguments, bool capture)
        {
            var psi = new ProcessStartInfo(PythonExe, arguments)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                WindowStyle = ProcessWindowStyle.Hidden,
                WorkingDirectory = Root,
                RedirectStandardOutput = capture,
                RedirectStandardError = capture,
            };
            if (capture)
            {
                psi.StandardOutputEncoding = Encoding.UTF8;
                psi.StandardErrorEncoding = Encoding.UTF8;
            }
            psi.EnvironmentVariables["APT_DATA_DIR"] = DataDir;
            psi.EnvironmentVariables["PYTHONUTF8"] = "1";
            psi.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
            string ocr = Path.Combine(Root, "ocr"), gs = Path.Combine(Root, "gs");
            if (Directory.Exists(ocr)) psi.EnvironmentVariables["APT_OCR_DIR"] = ocr;
            if (Directory.Exists(gs)) psi.EnvironmentVariables["APT_GS_DIR"] = gs;
            return Process.Start(psi);
        }

        /// <summary>Stop a process and everything it started (taskkill /T).</summary>
        public static void KillTree(Process p)
        {
            if (p == null) return;
            try
            {
                if (p.HasExited) return;
                var psi = new ProcessStartInfo("taskkill", "/PID " + p.Id + " /T /F")
                {
                    UseShellExecute = false,
                    CreateNoWindow = true,
                    WindowStyle = ProcessWindowStyle.Hidden,
                };
                using (var k = Process.Start(psi)) { k.WaitForExit(10000); }
                p.WaitForExit(5000);
            }
            catch (Exception) { }
        }
    }

    /// <summary>key=value settings in data\launcher.ini.</summary>
    class Settings
    {
        readonly string path = Path.Combine(Launcher.DataDir, "launcher.ini");
        readonly Dictionary<string, string> values = new Dictionary<string, string>();

        public Settings()
        {
            try
            {
                foreach (var line in File.ReadAllLines(path))
                {
                    int eq = line.IndexOf('=');
                    if (eq > 0) values[line.Substring(0, eq).Trim()] = line.Substring(eq + 1).Trim();
                }
            }
            catch (Exception) { }
        }

        public bool Get(string key, bool fallback)
        {
            string v;
            return values.TryGetValue(key, out v) ? v == "1" : fallback;
        }

        public void Set(string key, bool value)
        {
            values[key] = value ? "1" : "0";
            try
            {
                Directory.CreateDirectory(Launcher.DataDir);
                var sb = new StringBuilder();
                foreach (var kv in values) sb.Append(kv.Key).Append('=').Append(kv.Value).Append("\r\n");
                File.WriteAllText(path, sb.ToString());
            }
            catch (Exception) { }
        }
    }

    class LauncherForm : Form
    {
        readonly JavaScriptSerializer json = new JavaScriptSerializer();
        readonly Settings settings = new Settings();
        readonly ListView list = new ListView();
        readonly Label status = new Label();
        readonly Label subtitle = new Label();
        readonly TextBox info = new TextBox();
        readonly ProgressBar progress = new ProgressBar();
        readonly CheckBox lanBox = new CheckBox();
        readonly CheckBox updatesBox = new CheckBox();
        readonly Button openButton = new Button();
        readonly Button updateButton = new Button();
        readonly Button moreButton = new Button();
        readonly Button hideButton = new Button();
        readonly Button exitButton = new Button();
        readonly ContextMenuStrip moreMenu = new ContextMenuStrip();
        readonly NotifyIcon tray = new NotifyIcon();
        readonly object logLock = new object();
        Process server;
        StreamWriter log;
        bool exiting, trayHintShown, firstStart = true;
        string updatePage;
        Dictionary<string, object> pendingUpdate;

        public LauncherForm()
        {
            Text = "Admin PDF Toolkit";
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch (Exception) { }
            Font = new Font("Segoe UI", 9.5f);
            AutoScaleMode = AutoScaleMode.Font;
            ClientSize = new Size(700, 600);
            MinimumSize = new Size(560, 480);
            StartPosition = FormStartPosition.CenterScreen;

            var title = new Label
            {
                Text = "Admin PDF Toolkit",
                Font = new Font("Segoe UI Semibold", 15f),
                AutoSize = true,
                Margin = new Padding(0, 0, 0, 2),
            };
            subtitle.Text = T("Bileşenler denetleniyor…", "Checking components…");
            subtitle.AutoSize = true;
            subtitle.ForeColor = SystemColors.GrayText;

            list.View = View.Details;
            list.FullRowSelect = true;
            list.HeaderStyle = ColumnHeaderStyle.Nonclickable;
            list.Dock = DockStyle.Fill;
            list.Columns.Add("", 34);
            list.Columns.Add(T("Bileşen", "Component"), 190);
            list.Columns.Add(T("Sürüm", "Version"), 150);
            list.Columns.Add(T("Ayrıntı", "Details"), 300);
            list.ShowItemToolTips = true;

            status.AutoSize = false;
            status.AutoEllipsis = true;
            status.Dock = DockStyle.Fill;
            status.Font = new Font("Segoe UI Semibold", 10.5f);
            status.Text = T("Denetleniyor…", "Checking…");
            progress.Style = ProgressBarStyle.Marquee;
            progress.Dock = DockStyle.Fill;
            progress.Height = 8;

            info.Multiline = true;
            info.ReadOnly = true;
            info.Dock = DockStyle.Fill;
            info.Height = 96;
            info.ScrollBars = ScrollBars.Vertical;
            info.BackColor = SystemColors.Window;

            lanBox.Text = T("Ağ paylaşımı (aynı ağdaki telefon / tablet)", "Network sharing (phones / tablets on this network)");
            lanBox.AutoSize = true;
            lanBox.Checked = settings.Get("lan", false);
            lanBox.CheckedChanged += delegate { settings.Set("lan", lanBox.Checked); RestartServer(); };
            updatesBox.Text = T("Açılışta güncellemeleri denetle", "Check for updates at start");
            updatesBox.AutoSize = true;
            updatesBox.Checked = settings.Get("check_updates", true);
            updatesBox.CheckedChanged += delegate { settings.Set("check_updates", updatesBox.Checked); };

            SetupButton(openButton, T("Tarayıcıda aç", "Open in browser"), delegate { Launcher.OpenUrl(Launcher.AppUrl()); });
            SetupButton(updateButton, T("Güncellemeleri denetle", "Check for updates"), delegate { OnUpdateButton(); });
            SetupButton(moreButton, T("Diğer ▾", "More ▾"), delegate { moreMenu.Show(moreButton, 0, moreButton.Height); });
            SetupButton(hideButton, T("Arka plana gizle", "Hide to tray"), delegate { HideToTray(); });
            SetupButton(exitButton, T("Çıkış", "Exit"), delegate { ExitApp(); });
            openButton.Enabled = false;

            moreMenu.Items.Add(T("Sertifikaya bu bilgisayarda güven", "Trust the certificate on this PC"), null, delegate { TrustCertificate(); });
            moreMenu.Items.Add(T("OCR dosyalarını denetle / onar", "Check / repair OCR files"), null, delegate { RepairOcr(); });
            moreMenu.Items.Add(T("Sunucu günlüğü", "Server log"), null, delegate { OpenPath(Path.Combine(Launcher.DataDir, "server.log")); });
            moreMenu.Items.Add(T("Uygulama klasörü", "App folder"), null, delegate { OpenPath(Launcher.Root); });

            var buttons = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, WrapContents = true };
            buttons.Controls.AddRange(new Control[] { openButton, updateButton, moreButton, hideButton, exitButton });
            var options = new FlowLayoutPanel { Dock = DockStyle.Fill, AutoSize = true, FlowDirection = FlowDirection.TopDown };
            options.Controls.AddRange(new Control[] { lanBox, updatesBox });

            var layout = new TableLayoutPanel { Dock = DockStyle.Fill, Padding = new Padding(14), ColumnCount = 1 };
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 46));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Absolute, 104));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.Controls.Add(title);
            layout.Controls.Add(subtitle);
            layout.Controls.Add(list);
            layout.Controls.Add(status);
            layout.Controls.Add(progress);
            layout.Controls.Add(info);
            layout.Controls.Add(options);
            layout.Controls.Add(buttons);
            Controls.Add(layout);

            var trayMenu = new ContextMenuStrip();
            trayMenu.Items.Add(T("Göster", "Show"), null, delegate { ShowFromTray(); });
            trayMenu.Items.Add(T("Tarayıcıda aç", "Open in browser"), null, delegate { Launcher.OpenUrl(Launcher.AppUrl()); });
            trayMenu.Items.Add(new ToolStripSeparator());
            trayMenu.Items.Add(T("Çıkış", "Exit"), null, delegate { ExitApp(); });
            tray.Icon = Icon ?? SystemIcons.Application;
            tray.Text = "Admin PDF Toolkit";
            tray.ContextMenuStrip = trayMenu;
            tray.Visible = true;
            tray.DoubleClick += delegate { ShowFromTray(); };

            Shown += delegate { CleanupOldFiles(); RunInBackground(RunChecks); };
            Resize += delegate { if (WindowState == FormWindowState.Minimized) HideToTray(); };
            FormClosing += OnClosing;
        }

        static string T(string tr, string en) { return Launcher.T(tr, en); }

        static void SetupButton(Button b, string text, EventHandler click)
        {
            b.Text = text;
            b.AutoSize = true;
            b.Padding = new Padding(8, 2, 8, 2);
            b.Click += click;
        }

        void Ui(Action action)
        {
            if (IsDisposed) return;
            try { BeginInvoke(action); } catch (InvalidOperationException) { }
        }

        static void RunInBackground(ThreadStart work)
        {
            new Thread(work) { IsBackground = true }.Start();
        }

        Dictionary<string, object> Parse(string line)
        {
            if (string.IsNullOrEmpty(line) || line[0] != '{') return null;
            try { return json.Deserialize<Dictionary<string, object>>(line); }
            catch (Exception) { return null; }
        }

        static string Str(Dictionary<string, object> d, string key)
        {
            object v;
            return d != null && d.TryGetValue(key, out v) && v != null ? v.ToString() : "";
        }

        static string Txt(Dictionary<string, object> d, string key)
        {
            object v;
            var t = d != null && d.TryGetValue(key, out v) ? v as Dictionary<string, object> : null;
            return t == null ? "" : (Launcher.Tr ? Str(t, "tr") : Str(t, "en"));
        }

        // ---- 1. component checks ---------------------------------------------
        void RunChecks()
        {
            Dictionary<string, object> done = null;
            try
            {
                using (var p = Launcher.StartPython("-m adminpdf.selfcheck", true))
                {
                    p.ErrorDataReceived += delegate { };
                    p.BeginErrorReadLine();
                    string line;
                    while ((line = p.StandardOutput.ReadLine()) != null)
                    {
                        var d = Parse(line);
                        if (d == null) continue;
                        if (Str(d, "type") == "check") { var row = d; Ui(delegate { AddRow(row); }); }
                        else if (Str(d, "type") == "done") done = d;
                    }
                    p.WaitForExit();
                }
            }
            catch (Exception e)
            {
                Ui(delegate { Fail(T("Python başlatılamadı: ", "Could not start Python: ") + e.Message); });
                return;
            }
            var result = done;
            Ui(delegate { ChecksFinished(result); });
        }

        void AddRow(Dictionary<string, object> d)
        {
            string s = Str(d, "status");
            string mark = s == "ok" ? "✔" : s == "warn" ? "⚠" : s == "missing" ? "–" : "✖";
            var item = new ListViewItem(new[] { mark, Txt(d, "title"), Str(d, "version"), Txt(d, "detail") });
            item.ToolTipText = Txt(d, "detail");
            item.ForeColor = s == "ok" ? Color.FromArgb(24, 121, 78)
                : s == "warn" ? Color.FromArgb(154, 91, 0)
                : s == "missing" ? SystemColors.GrayText
                : Color.FromArgb(196, 38, 46);
            list.Items.Add(item);
            item.EnsureVisible();
        }

        void ChecksFinished(Dictionary<string, object> done)
        {
            subtitle.Text = string.Format(T("{0} bileşen denetlendi", "{0} components checked"), list.Items.Count);
            bool ready = done != null && done.ContainsKey("ready") && true.Equals(done["ready"]);
            if (!ready)
            {
                Fail(T("Sistem hazır değil — kırmızı satırlara bakın.", "Not ready — see the red rows."));
                return;
            }
            var data = done["info"] as Dictionary<string, object>;
            ShowInfo(data);
            StartServer();
        }

        void ShowInfo(Dictionary<string, object> data)
        {
            var sb = new StringBuilder();
            sb.Append(T("Adres: ", "Address: ")).Append(Launcher.AppUrl()).Append("\r\n");
            var lan = data != null && data.ContainsKey("lan_urls") ? data["lan_urls"] as System.Collections.ArrayList : null;
            if (lan != null && lan.Count > 0)
            {
                sb.Append(T("Yerel ağ: ", "Local network: "));
                for (int i = 0; i < lan.Count; i++) sb.Append(i > 0 ? ", " : "").Append(lan[i]);
                sb.Append(T("  (telefon için uygulamada 📱 Cihaz bağla)", "  (phones: 📱 Connect device in the app)")).Append("\r\n");
            }
            sb.Append(T("Sertifika parmak izi: ", "Certificate fingerprint: ")).Append(Str(data, "fingerprint")).Append("…\r\n");
            sb.Append(T("Veri klasörü: ", "Data folder: ")).Append(Str(data, "data_dir")).Append("\r\n");
            sb.Append(T("Sürüm: ", "Version: ")).Append(Str(data, "version"));
            info.Text = sb.ToString();
        }

        void Fail(string message)
        {
            status.Text = "✖ " + message;
            status.ForeColor = Color.FromArgb(196, 38, 46);
            progress.Visible = false;
        }

        // ---- 2. the server --------------------------------------------------------
        void StartServer()
        {
            status.Text = T("Sunucu başlatılıyor…", "Starting the server…");
            status.ForeColor = SystemColors.ControlText;
            progress.Visible = true;
            progress.Style = ProgressBarStyle.Marquee;
            string args = "-m adminpdf" + (lanBox.Checked ? " --lan" : "") + (firstStart ? " --open" : "");
            firstStart = false;
            try
            {
                Directory.CreateDirectory(Launcher.DataDir);
                lock (logLock)
                {
                    if (log == null)
                        log = new StreamWriter(Path.Combine(Launcher.DataDir, "server.log"), false, new UTF8Encoding(false)) { AutoFlush = true };
                }
                server = Launcher.StartPython(args, true);
                server.OutputDataReceived += WriteLog;
                server.ErrorDataReceived += WriteLog;
                server.BeginOutputReadLine();
                server.BeginErrorReadLine();
            }
            catch (Exception e)
            {
                Fail(T("Sunucu başlatılamadı: ", "Could not start the server: ") + e.Message);
                return;
            }
            var started = server;
            RunInBackground(delegate { WaitForServer(started); });
        }

        void WriteLog(object sender, DataReceivedEventArgs e)
        {
            if (e.Data == null) return;
            lock (logLock) { if (log != null) log.WriteLine(e.Data); }
        }

        void WaitForServer(Process p)
        {
            for (int i = 0; i < 120; i++)
            {
                if (p.HasExited)
                {
                    Ui(delegate { Fail(T("Sunucu kapandı — ayrıntı: Diğer ▸ Sunucu günlüğü.", "The server stopped — see More ▸ Server log.")); });
                    return;
                }
                try
                {
                    using (var c = new TcpClient())
                    {
                        c.Connect("127.0.0.1", Launcher.Port());
                        Ui(ServerReady);
                        return;
                    }
                }
                catch (SocketException) { Thread.Sleep(500); }
            }
            Ui(delegate { Fail(T("Sunucu yanıt vermiyor.", "The server does not respond.")); });
        }

        void ServerReady()
        {
            status.Text = "✔ " + T("Sistem hazır", "System ready") + (lanBox.Checked ? T(" · ağ paylaşımı açık", " · network sharing on") : "");
            status.ForeColor = Color.FromArgb(24, 121, 78);
            progress.Visible = false;
            openButton.Enabled = true;
            tray.Text = "Admin PDF Toolkit — " + T("hazır", "ready");
            if (updatesBox.Checked && pendingUpdate == null) RunInBackground(CheckUpdates);
        }

        void StopServer()
        {
            var p = server;
            server = null;
            Launcher.KillTree(p);
        }

        void RestartServer()
        {
            if (server == null) return;
            openButton.Enabled = false;
            StopServer();
            StartServer();
        }

        // ---- 3. updates ---------------------------------------------------------------
        void CheckUpdates()
        {
            Dictionary<string, object> result = null;
            try
            {
                using (var p = Launcher.StartPython("-m adminpdf.updater check", true))
                {
                    p.ErrorDataReceived += delegate { };
                    p.BeginErrorReadLine();
                    string line;
                    while ((line = p.StandardOutput.ReadLine()) != null) { var d = Parse(line); if (d != null) result = d; }
                    p.WaitForExit();
                }
            }
            catch (Exception) { }
            var r = result;
            Ui(delegate { UpdateChecked(r); });
        }

        void UpdateChecked(Dictionary<string, object> r)
        {
            if (r == null || !true.Equals(r["ok"]))
            {
                updateButton.Text = T("Güncelleme denetlenemedi", "Update check failed");
                tray.ShowBalloonTip(4000, "Admin PDF Toolkit",
                    T("Güncellemeler denetlenemedi (ağ engelli olabilir). Uygulama çalışıyor.", "Could not check for updates (the network may block it). The app is running."),
                    ToolTipIcon.None);
                return;
            }
            if (!true.Equals(r["available"]))
            {
                updateButton.Text = T("Güncel ✔", "Up to date ✔");
                return;
            }
            pendingUpdate = r;
            updatePage = Str(r, "page");
            string latest = Str(r, "latest");
            updateButton.Text = T("Güncelle: v", "Update: v") + latest;
            var comps = r.ContainsKey("components") ? r["components"] as Dictionary<string, object> : null;
            var sb = new StringBuilder();
            sb.Append(string.Format(T("Yeni sürüm var: v{0} (şu an v{1}).", "A new version is available: v{0} (now v{1})."), latest, Str(r, "current")));
            if (comps != null && comps.Count > 0)
            {
                sb.Append("\r\n\r\n").Append(T("İçerdiği bileşenler:", "Bundled components:"));
                foreach (var kv in comps) sb.Append("\r\n  • ").Append(kv.Key).Append(' ').Append(kv.Value);
            }
            if (true.Equals(r["installable"]))
            {
                sb.Append("\r\n\r\n").Append(T("İmzası doğrulanarak indirilip kurulsun mu? (Sunucu kısa süre kapanır; verileriniz ve sertifikanız korunur.)",
                    "Download and install it, signature-verified? (The server stops briefly; your data and certificate are kept.)"));
                if (MessageBox.Show(this, sb.ToString(), "Admin PDF Toolkit", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes)
                    InstallUpdate();
            }
            else
            {
                sb.Append("\r\n\r\n").Append(T("Bu sürüm otomatik kurulamıyor (imza yok). İndirme sayfası açılsın mı?",
                    "This release cannot be installed automatically (unsigned). Open the download page?"));
                if (MessageBox.Show(this, sb.ToString(), "Admin PDF Toolkit", MessageBoxButtons.YesNo, MessageBoxIcon.Information) == DialogResult.Yes)
                    Launcher.OpenUrl(updatePage);
            }
        }

        void OnUpdateButton()
        {
            if (pendingUpdate == null) { updateButton.Text = T("Denetleniyor…", "Checking…"); RunInBackground(CheckUpdates); return; }
            if (true.Equals(pendingUpdate["installable"])) InstallUpdate();
            else Launcher.OpenUrl(updatePage);
        }

        void InstallUpdate()
        {
            updateButton.Enabled = false;
            openButton.Enabled = false;
            StopServer();
            status.Text = T("Güncelleme indiriliyor ve doğrulanıyor…", "Downloading and verifying the update…");
            status.ForeColor = SystemColors.ControlText;
            progress.Visible = true;
            progress.Style = ProgressBarStyle.Continuous;
            progress.Value = 0;
            RunInBackground(DownloadUpdate);
        }

        void DownloadUpdate()
        {
            string staged = null, error = null;
            string dest = Path.Combine(Launcher.Root, "_update");
            try
            {
                using (var p = Launcher.StartPython("-m adminpdf.updater download --dest \"" + dest + "\"", true))
                {
                    p.ErrorDataReceived += delegate { };
                    p.BeginErrorReadLine();
                    string line;
                    while ((line = p.StandardOutput.ReadLine()) != null)
                    {
                        var d = Parse(line);
                        if (d == null) continue;
                        string type = Str(d, "type");
                        if (type == "progress")
                        {
                            int pct = (int)(Convert.ToDouble(d["fraction"], CultureInfo.InvariantCulture) * 100);
                            Ui(delegate { progress.Value = Math.Max(0, Math.Min(100, pct)); });
                        }
                        else if (type == "staged") staged = Str(d, "path");
                        else if (type == "error") error = Str(d, "message");
                    }
                    p.WaitForExit();
                }
            }
            catch (Exception e) { error = e.Message; }
            if (staged == null)
            {
                var msg = error ?? "?";
                Ui(delegate
                {
                    Fail(T("Güncelleme kurulmadı: ", "Update not installed: ") + msg);
                    updateButton.Enabled = true;
                    StartServer();
                });
                return;
            }
            try { ApplyUpdate(staged); }
            catch (Exception e)
            {
                var msg = e.Message;
                Ui(delegate { Fail(T("Güncelleme uygulanamadı: ", "Could not apply the update: ") + msg); });
                return;
            }
            Ui(delegate
            {
                exiting = true;
                tray.Visible = false;
                try { Process.Start(Path.Combine(Launcher.Root, "AdminPDFToolkit.exe")); } catch (Exception) { }
                Application.Exit();
            });
        }

        /// <summary>Swap the verified new files in. data\ (uploads, certificate,
        /// settings) is never touched; replaced folders and the running exe are
        /// moved aside and removed on the next start.</summary>
        static void ApplyUpdate(string staged)
        {
            string old = Path.Combine(Launcher.Root, "_old");
            Directory.CreateDirectory(old);
            string stamp = DateTime.Now.Ticks.ToString(CultureInfo.InvariantCulture);
            foreach (var dir in Directory.GetDirectories(staged))
            {
                string name = Path.GetFileName(dir);
                if (string.Equals(name, "data", StringComparison.OrdinalIgnoreCase)) continue;
                string target = Path.Combine(Launcher.Root, name);
                if (Directory.Exists(target)) Directory.Move(target, Path.Combine(old, name + "." + stamp));
                Directory.Move(dir, target);
            }
            foreach (var file in Directory.GetFiles(staged))
            {
                string target = Path.Combine(Launcher.Root, Path.GetFileName(file));
                if (File.Exists(target))
                {
                    // A running exe cannot be deleted but can be renamed.
                    File.Move(target, Path.Combine(old, Path.GetFileName(file) + "." + stamp));
                }
                File.Move(file, target);
            }
            try { Directory.Delete(Path.Combine(Launcher.Root, "_update"), true); } catch (Exception) { }
        }

        static void CleanupOldFiles()
        {
            try { Directory.Delete(Path.Combine(Launcher.Root, "_old"), true); } catch (Exception) { }
            try { Directory.Delete(Path.Combine(Launcher.Root, "_update"), true); } catch (Exception) { }
        }

        // ---- extras -------------------------------------------------------------------
        void TrustCertificate()
        {
            RunInBackground(delegate
            {
                try { using (var p = Launcher.StartPython("-m adminpdf --trust-ca", false)) p.WaitForExit(); }
                catch (Exception) { }
            });
        }

        static void RepairOcr()
        {
            string script = Path.Combine(Launcher.Root, "scripts\\repair-ocr-windows.ps1");
            string ocr = Path.Combine(Launcher.Root, "ocr");
            try
            {
                // Visible on purpose: the user asked for it and should see the result.
                Process.Start(new ProcessStartInfo("powershell",
                    "-NoProfile -ExecutionPolicy Bypass -NoExit -File \"" + script + "\" -OcrDir \"" + ocr + "\"") { UseShellExecute = true });
            }
            catch (Exception) { }
        }

        static void OpenPath(string path)
        {
            try { Process.Start(new ProcessStartInfo(path) { UseShellExecute = true }); } catch (Exception) { }
        }

        // ---- tray -----------------------------------------------------------------
        void HideToTray()
        {
            Hide();
            if (!trayHintShown)
            {
                trayHintShown = true;
                tray.ShowBalloonTip(4000, "Admin PDF Toolkit",
                    T("Arka planda çalışıyor. Açmak için simgeye çift tıklayın.", "Running in the background. Double-click the icon to open."),
                    ToolTipIcon.Info);
            }
        }

        void ShowFromTray()
        {
            Show();
            WindowState = FormWindowState.Normal;
            Activate();
        }

        void OnClosing(object sender, FormClosingEventArgs e)
        {
            if (!exiting && e.CloseReason == CloseReason.UserClosing)
            {
                // The window's ✕ keeps the server running in the tray; Exit stops it.
                e.Cancel = true;
                HideToTray();
                return;
            }
            StopServer();
            tray.Visible = false;
        }

        void ExitApp()
        {
            exiting = true;
            StopServer();
            tray.Visible = false;
            lock (logLock) { if (log != null) { log.Dispose(); log = null; } }
            Application.Exit();
        }
    }
}
