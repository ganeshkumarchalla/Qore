// QORE Desktop Professional Graphite Installer Wizard (C# 5 / .NET Framework 4.x)
// Custom borderless Graphite UI with 5-step sidebar rail, system preflight cards,
// workspace/AI/runtime customizations, smooth custom progress bar, shortcuts,
// and uninstaller registration. Supports /SILENT /DIR=<path> and --preview-dir=<dir>.

using System;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using Microsoft.Win32;

[assembly: AssemblyTitle("QORE Desktop Setup")]
[assembly: AssemblyDescription("Professional Graphite Installer for QORE Desktop")]
[assembly: AssemblyCompany("QORE")]
[assembly: AssemblyProduct("QORE Desktop Setup")]
[assembly: AssemblyVersion("0.1.0.0")]
[assembly: AssemblyFileVersion("0.1.0.0")]

namespace QoreInstaller
{
    static class Program
    {
        [STAThread]
        static int Main(string[] args)
        {
            bool silent = false;
            string customDir = null;
            string previewDir = null;
            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], "/SILENT", StringComparison.OrdinalIgnoreCase) ||
                    string.Equals(args[i], "--silent", StringComparison.OrdinalIgnoreCase))
                {
                    silent = true;
                }
                else if (args[i].StartsWith("/DIR=", StringComparison.OrdinalIgnoreCase))
                {
                    customDir = args[i].Substring(5).Trim('"');
                }
                else if (args[i].StartsWith("--preview-dir=", StringComparison.OrdinalIgnoreCase))
                {
                    previewDir = args[i].Substring(14).Trim('"');
                }
            }

            string sourceRoot = ResolveSourceRoot();
            string defaultInstallDir = customDir ?? Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                "Programs",
                "QORE"
            );

            if (silent)
            {
                InstallOptions opts = new InstallOptions
                {
                    SourceRoot = sourceRoot,
                    TargetDir = defaultInstallDir,
                    DataDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "QORE", "data"),
                    IncludeAiModel = true,
                    CreateDesktopShortcut = false,
                    CreateStartMenuShortcut = false,
                    RegisterUninstaller = true,
                    LaunchMode = "app",
                    SimMethod = "statevector",
                    DefaultShots = "1024",
                    ForgeLevel = "2"
                };
                string err = PerformInstall(opts, delegate(int pct, string msg) { Console.WriteLine(pct + "%: " + msg); });
                if (!string.IsNullOrEmpty(err))
                {
                    Console.Error.WriteLine(err);
                    return 1;
                }
                Console.WriteLine("QORE installed successfully to " + opts.TargetDir);
                return 0;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            InstallerWizardForm form = new InstallerWizardForm(sourceRoot, defaultInstallDir);
            if (!string.IsNullOrEmpty(previewDir))
            {
                form.ExportPreviewScreenshots(previewDir);
                form.Dispose();
                return 0;
            }
            Application.Run(form);
            return 0;
        }

        public static string ResolveSourceRoot()
        {
            string exeDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            string probe = exeDir;
            for (int i = 0; i < 4; i++)
            {
                if (Directory.Exists(Path.Combine(probe, "backend")) &&
                    Directory.Exists(Path.Combine(probe, "frontend", "dist")))
                {
                    return probe;
                }
                DirectoryInfo parent = Directory.GetParent(probe);
                if (parent == null) break;
                probe = parent.FullName;
            }
            return exeDir;
        }

        public static string ResolvePythonPath(string sourceRoot)
        {
            string[] candidates = new string[]
            {
                Path.Combine(sourceRoot, ".venv", "Scripts", "python.exe"),
                @"C:\Users\ganes\OneDrive\QORE\.venv\Scripts\python.exe"
            };
            for (int i = 0; i < candidates.Length; i++)
            {
                if (File.Exists(candidates[i])) return candidates[i];
            }
            string pathEnv = Environment.GetEnvironmentVariable("PATH") ?? "";
            string[] dirs = pathEnv.Split(';');
            for (int i = 0; i < dirs.Length; i++)
            {
                if (string.IsNullOrEmpty(dirs[i])) continue;
                string py = Path.Combine(dirs[i].Trim(), "python.exe");
                if (File.Exists(py)) return py;
            }
            return "";
        }

        public static bool HasEdgeDesktopHost()
        {
            string[] edges = new string[]
            {
                @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                @"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), @"Microsoft\Edge\Application\msedge.exe")
            };
            for (int i = 0; i < edges.Length; i++)
            {
                if (File.Exists(edges[i])) return true;
            }
            return false;
        }

        public class InstallOptions
        {
            public string SourceRoot;
            public string TargetDir;
            public string DataDir;
            public bool IncludeAiModel;
            public bool CreateDesktopShortcut;
            public bool CreateStartMenuShortcut;
            public bool RegisterUninstaller;
            public string LaunchMode;
            public string SimMethod;
            public string DefaultShots;
            public string ForgeLevel;
        }

        public static string PerformInstall(InstallOptions opts, Action<int, string> onProgress)
        {
            try
            {
                onProgress(8, "Validating QORE payload at " + opts.SourceRoot);
                string backendSrc = Path.Combine(opts.SourceRoot, "backend");
                string distSrc = Path.Combine(opts.SourceRoot, "frontend", "dist");
                if (!Directory.Exists(backendSrc) || !Directory.Exists(distSrc))
                {
                    return "Missing QORE backend/ or frontend/dist/ payload in " + opts.SourceRoot;
                }

                Directory.CreateDirectory(opts.TargetDir);
                Directory.CreateDirectory(opts.DataDir);
                onProgress(18, "Copying QORE-Desktop.exe host launcher...");
                string launcherSrc = Path.Combine(opts.SourceRoot, "QORE-Desktop.exe");
                if (!File.Exists(launcherSrc)) launcherSrc = Path.Combine(opts.SourceRoot, "dist", "desktop", "QORE-Desktop.exe");
                if (!File.Exists(launcherSrc)) launcherSrc = Path.Combine(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\'), "QORE-Desktop.exe");
                if (!File.Exists(launcherSrc)) return "Missing QORE-Desktop.exe launcher binary.";

                string targetExe = Path.Combine(opts.TargetDir, "QORE-Desktop.exe");
                File.Copy(launcherSrc, targetExe, true);

                onProgress(38, "Installing QORE backend engine, Qiskit IR & Forge...");
                CopyDirectory(backendSrc, Path.Combine(opts.TargetDir, "backend"), opts.IncludeAiModel, new string[] { "__pycache__", ".pytest_cache", "tests" });

                onProgress(62, "Installing Graphite Studio/Lab/Forge frontend bundle...");
                CopyDirectory(distSrc, Path.Combine(opts.TargetDir, "frontend", "dist"), true, new string[] { });

                onProgress(76, "Writing customized desktop & runtime preferences...");
                string pythonExe = ResolvePythonPath(opts.SourceRoot);
                string cfgJson = "{\n" +
                    "  \"python_executable\": \"" + pythonExe.Replace("\\", "\\\\") + "\",\n" +
                    "  \"data_dir\": \"" + opts.DataDir.Replace("\\", "\\\\") + "\",\n" +
                    "  \"launch_mode\": \"" + (opts.LaunchMode ?? "app") + "\",\n" +
                    "  \"default_simulation_method\": \"" + (opts.SimMethod ?? "statevector") + "\",\n" +
                    "  \"default_shots\": " + (opts.DefaultShots ?? "1024") + ",\n" +
                    "  \"default_forge_level\": " + (opts.ForgeLevel ?? "2") + ",\n" +
                    "  \"ai_model\": \"" + (opts.IncludeAiModel ? "qore-quantum-rl-dl-v1" : "disabled") + "\",\n" +
                    "  \"installed_at\": \"" + DateTime.UtcNow.ToString("o") + "\"\n" +
                    "}\n";
                File.WriteAllText(Path.Combine(opts.TargetDir, "qore-desktop.json"), cfgJson, Encoding.UTF8);

                string uninstallCmd = Path.Combine(opts.TargetDir, "Uninstall-QORE.cmd");
                string uninstallScript = "@echo off\r\n" +
                    "echo Uninstalling QORE Desktop...\r\n" +
                    "reg delete \"HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\QORE\" /f >nul 2>&1\r\n" +
                    "del /q \"%USERPROFILE%\\Desktop\\QORE.lnk\" >nul 2>&1\r\n" +
                    "rmdir /s /q \"%APPDATA%\\Microsoft\\Windows\\Start Menu\\Programs\\QORE\" >nul 2>&1\r\n" +
                    "rmdir /s /q \"" + opts.TargetDir + "\"\r\n";
                File.WriteAllText(uninstallCmd, uninstallScript, Encoding.ASCII);

                if (opts.CreateDesktopShortcut)
                {
                    onProgress(86, "Creating Desktop shortcut (QORE.lnk)...");
                    string desktopLnk = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "QORE.lnk");
                    CreateShortcut(desktopLnk, targetExe, opts.TargetDir, "QORE — The Core of Quantum Development");
                }

                if (opts.CreateStartMenuShortcut)
                {
                    onProgress(92, "Creating Start Menu entry...");
                    string startDir = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "QORE");
                    Directory.CreateDirectory(startDir);
                    CreateShortcut(Path.Combine(startDir, "QORE.lnk"), targetExe, opts.TargetDir, "QORE — The Core of Quantum Development");
                    CreateShortcut(Path.Combine(startDir, "Uninstall QORE.lnk"), uninstallCmd, opts.TargetDir, "Uninstall QORE Desktop");
                }

                if (opts.RegisterUninstaller)
                {
                    onProgress(96, "Registering QORE in Windows Apps & Features...");
                    using (RegistryKey key = Registry.CurrentUser.CreateSubKey(@"Software\Microsoft\Windows\CurrentVersion\Uninstall\QORE"))
                    {
                        if (key != null)
                        {
                            key.SetValue("DisplayName", "QORE Desktop — Quantum Development Environment");
                            key.SetValue("DisplayVersion", "0.1.0");
                            key.SetValue("Publisher", "QORE");
                            key.SetValue("InstallLocation", opts.TargetDir);
                            key.SetValue("DisplayIcon", targetExe);
                            key.SetValue("UninstallString", "\"" + uninstallCmd + "\"");
                            key.SetValue("NoModify", 1, RegistryValueKind.DWord);
                            key.SetValue("NoRepair", 1, RegistryValueKind.DWord);
                        }
                    }
                }

                onProgress(100, "Installation completed cleanly.");
                return null;
            }
            catch (Exception ex)
            {
                return "Install failed: " + ex.Message;
            }
        }

        private static void CopyDirectory(string sourceDir, string targetDir, bool includeAiModel, string[] skipNames)
        {
            Directory.CreateDirectory(targetDir);
            string[] files = Directory.GetFiles(sourceDir);
            for (int i = 0; i < files.Length; i++)
            {
                string name = Path.GetFileName(files[i]);
                if (!includeAiModel && (name == "qore_ai_model.joblib" || name == "qore_ai_metrics.json")) continue;
                File.Copy(files[i], Path.Combine(targetDir, name), true);
            }
            string[] dirs = Directory.GetDirectories(sourceDir);
            for (int i = 0; i < dirs.Length; i++)
            {
                string name = Path.GetFileName(dirs[i]);
                bool skip = false;
                for (int j = 0; j < skipNames.Length; j++)
                {
                    if (string.Equals(name, skipNames[j], StringComparison.OrdinalIgnoreCase)) { skip = true; break; }
                }
                if (!skip) CopyDirectory(dirs[i], Path.Combine(targetDir, name), includeAiModel, skipNames);
            }
        }

        private static void CreateShortcut(string shortcutPath, string targetPath, string workingDir, string description)
        {
            Type shellType = Type.GetTypeFromProgID("WScript.Shell");
            if (shellType == null) return;
            object shell = Activator.CreateInstance(shellType);
            object shortcut = shellType.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, shell, new object[] { shortcutPath });
            Type scType = shortcut.GetType();
            scType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
            scType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { workingDir });
            scType.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { description });
            scType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
        }
    }

    class GraphiteProgressBar : Control
    {
        private int _value = 0;
        public int Value
        {
            get { return _value; }
            set { _value = Math.Max(0, Math.Min(100, value)); Invalidate(); }
        }

        public GraphiteProgressBar()
        {
            DoubleBuffered = true;
            Height = 12;
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            Graphics g = e.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (SolidBrush bg = new SolidBrush(Color.FromArgb(28, 28, 31)))
            {
                g.FillRectangle(bg, 0, 0, Width, Height);
            }
            using (Pen border = new Pen(Color.FromArgb(56, 56, 60)))
            {
                g.DrawRectangle(border, 0, 0, Width - 1, Height - 1);
            }
            int fillW = (int)((Width - 2) * (_value / 100.0));
            if (fillW > 0)
            {
                using (LinearGradientBrush fill = new LinearGradientBrush(
                    new Rectangle(1, 1, Math.Max(2, fillW), Height - 2),
                    Color.FromArgb(244, 242, 238),
                    Color.FromArgb(196, 194, 189),
                    0f))
                {
                    g.FillRectangle(fill, 1, 1, fillW, Height - 2);
                }
            }
        }
    }

    class InstallerWizardForm : Form
    {
        private readonly string _sourceRoot;
        private int _step = 0;
        private Point _dragStart;
        private bool _dragging = false;

        private Panel _sidebarPanel;
        private Panel _contentPanel;
        private Button _backBtn;
        private Button _nextBtn;
        private Button _cancelBtn;

        private readonly Label[] _stepBadges = new Label[5];
        private readonly Label[] _stepLabels = new Label[5];
        private readonly string[] _stepNames = new string[]
        {
            "Welcome & Preflight",
            "Location & AI Model",
            "Runtime & Shortcuts",
            "Installing QORE",
            "Setup Complete"
        };

        // User customization controls
        private TextBox _dirBox;
        private TextBox _dataDirBox;
        private CheckBox _chkAiModel;
        private CheckBox _chkDesktop;
        private CheckBox _chkStartMenu;
        private CheckBox _chkUninstaller;
        private ComboBox _comboLaunchMode;
        private ComboBox _comboSimMethod;
        private ComboBox _comboShots;
        private ComboBox _comboForgeLevel;
        private GraphiteProgressBar _progressBar;
        private Label _progressPct;
        private Label _statusTitle;
        private TextBox _logBox;
        private CheckBox _chkLaunchNow;

        // Exact QORE Graphite Theme Palette
        private static readonly Color BgDeep = Color.FromArgb(14, 14, 15);
        private static readonly Color BgSurface = Color.FromArgb(20, 20, 22);
        private static readonly Color BgPanel = Color.FromArgb(27, 27, 29);
        private static readonly Color BgCard = Color.FromArgb(32, 32, 35);
        private static readonly Color BorderSubtle = Color.FromArgb(50, 50, 54);
        private static readonly Color BorderStrong = Color.FromArgb(74, 73, 70);
        private static readonly Color TextPrimary = Color.FromArgb(244, 242, 238);
        private static readonly Color TextSecondary = Color.FromArgb(202, 200, 195);
        private static readonly Color TextMuted = Color.FromArgb(145, 143, 138);
        private static readonly Color SilverAccent = Color.FromArgb(216, 214, 210);
        private static readonly Color OkGreen = Color.FromArgb(140, 214, 166);
        private static readonly Color WarnAmber = Color.FromArgb(232, 188, 118);

        public InstallerWizardForm(string sourceRoot, string defaultDir)
        {
            _sourceRoot = sourceRoot;
            Text = "QORE Desktop Setup";
            Size = new Size(820, 540);
            FormBorderStyle = FormBorderStyle.None;
            StartPosition = FormStartPosition.CenterScreen;
            BackColor = BgDeep;
            ForeColor = TextPrimary;
            Font = new Font("Segoe UI", 9.5f);
            DoubleBuffered = true;

            BuildChrome();
            InitializeCustomizationControls(defaultDir);
            ShowStep(0);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            using (Pen p = new Pen(BorderStrong))
            {
                e.Graphics.DrawRectangle(p, 0, 0, Width - 1, Height - 1);
            }
        }

        private void AttachDrag(Control c)
        {
            c.MouseDown += delegate(object s, MouseEventArgs e)
            {
                if (e.Button == MouseButtons.Left) { _dragging = true; _dragStart = e.Location; }
            };
            c.MouseMove += delegate(object s, MouseEventArgs e)
            {
                if (_dragging) Location = new Point(Location.X + e.X - _dragStart.X, Location.Y + e.Y - _dragStart.Y);
            };
            c.MouseUp += delegate { _dragging = false; };
        }

        private void BuildChrome()
        {
            // Custom Graphite Top Titlebar (38px)
            Panel titleBar = new Panel { Dock = DockStyle.Top, Height = 38, BackColor = BgSurface };
            titleBar.Paint += delegate(object s, PaintEventArgs e)
            {
                using (Pen p = new Pen(BorderSubtle)) e.Graphics.DrawLine(p, 0, 37, titleBar.Width, 37);
            };
            Label titleLbl = new Label
            {
                Text = "QORE DESKTOP INSTALLER · v0.1.0",
                ForeColor = TextMuted,
                Font = new Font("Consolas", 8.5f, FontStyle.Bold),
                AutoSize = true,
                Location = new Point(16, 11)
            };
            Button minBtn = new Button
            {
                Text = "—",
                Width = 38,
                Height = 37,
                Dock = DockStyle.Right,
                FlatStyle = FlatStyle.Flat,
                ForeColor = TextSecondary,
                BackColor = BgSurface
            };
            minBtn.FlatAppearance.BorderSize = 0;
            minBtn.Click += delegate { WindowState = FormWindowState.Minimized; };

            Button closeBtn = new Button
            {
                Text = "✕",
                Width = 42,
                Height = 37,
                Dock = DockStyle.Right,
                FlatStyle = FlatStyle.Flat,
                ForeColor = TextSecondary,
                BackColor = BgSurface
            };
            closeBtn.FlatAppearance.BorderSize = 0;
            closeBtn.Click += delegate { Close(); };

            titleBar.Controls.Add(titleLbl);
            titleBar.Controls.Add(minBtn);
            titleBar.Controls.Add(closeBtn);
            AttachDrag(titleBar);
            AttachDrag(titleLbl);

            // Left Step Navigation Rail (220px)
            _sidebarPanel = new Panel { Dock = DockStyle.Left, Width = 220, BackColor = BgSurface };
            _sidebarPanel.Paint += delegate(object s, PaintEventArgs e)
            {
                using (Pen p = new Pen(BorderSubtle)) e.Graphics.DrawLine(p, 219, 0, 219, _sidebarPanel.Height);
            };

            // Geometric QORE Emblem + Brand Header
            Panel emblem = new Panel { Location = new Point(22, 22), Size = new Size(34, 34), BackColor = Color.Transparent };
            emblem.Paint += delegate(object s, PaintEventArgs e)
            {
                Graphics g = e.Graphics;
                g.SmoothingMode = SmoothingMode.AntiAlias;
                using (LinearGradientBrush b = new LinearGradientBrush(new Rectangle(0, 0, 34, 34), TextPrimary, Color.FromArgb(180, 178, 173), 45f))
                using (Pen ring = new Pen(b, 2.2f))
                {
                    g.DrawEllipse(ring, 3, 3, 28, 28);
                    g.DrawLine(ring, 20, 20, 30, 30);
                }
            };
            Label brandName = new Label { Text = "QORE", ForeColor = TextPrimary, Font = new Font("Segoe UI", 12.5f, FontStyle.Bold), Location = new Point(64, 21), AutoSize = true };
            Label brandTag = new Label { Text = "QUANTUM WORKBENCH", ForeColor = TextMuted, Font = new Font("Consolas", 7.5f), Location = new Point(65, 42), AutoSize = true };
            _sidebarPanel.Controls.Add(emblem);
            _sidebarPanel.Controls.Add(brandName);
            _sidebarPanel.Controls.Add(brandTag);

            for (int i = 0; i < 5; i++)
            {
                int y = 88 + i * 44;
                Label badge = new Label
                {
                    Text = "0" + (i + 1),
                    Size = new Size(26, 22),
                    Location = new Point(22, y),
                    TextAlign = ContentAlignment.MiddleCenter,
                    Font = new Font("Consolas", 8f, FontStyle.Bold),
                    ForeColor = TextMuted,
                    BackColor = BgPanel
                };
                Label lbl = new Label
                {
                    Text = _stepNames[i],
                    Location = new Point(56, y + 2),
                    Size = new Size(150, 20),
                    Font = new Font("Segoe UI", 9f),
                    ForeColor = TextMuted,
                    UseMnemonic = false
                };
                _stepBadges[i] = badge;
                _stepLabels[i] = lbl;
                _sidebarPanel.Controls.Add(badge);
                _sidebarPanel.Controls.Add(lbl);
            }

            Label sideFooter = new Label
            {
                Text = "AI: qore-quantum-rl-dl-v1\nHost: Windows 10/11 (x64)\nStorage: Local SQLite",
                ForeColor = TextMuted,
                Font = new Font("Consolas", 7.8f),
                Location = new Point(22, 422),
                Size = new Size(180, 54)
            };
            _sidebarPanel.Controls.Add(sideFooter);

            // Bottom Action Footer (62px)
            Panel footer = new Panel { Dock = DockStyle.Bottom, Height = 62, BackColor = BgSurface };
            footer.Paint += delegate(object s, PaintEventArgs e)
            {
                using (Pen p = new Pen(BorderSubtle)) e.Graphics.DrawLine(p, 0, 0, footer.Width, 0);
            };
            _cancelBtn = new Button
            {
                Text = "Cancel",
                Width = 90,
                Height = 34,
                Location = new Point(20, 14),
                FlatStyle = FlatStyle.Flat,
                ForeColor = TextSecondary,
                BackColor = BgPanel
            };
            _cancelBtn.FlatAppearance.BorderColor = BorderSubtle;
            _cancelBtn.Click += delegate { Close(); };

            _backBtn = new Button
            {
                Text = "← Back",
                Width = 96,
                Height = 34,
                Location = new Point(368, 14),
                FlatStyle = FlatStyle.Flat,
                ForeColor = TextPrimary,
                BackColor = BgPanel
            };
            _backBtn.FlatAppearance.BorderColor = BorderSubtle;
            _backBtn.Click += delegate { if (_step > 0 && _step < 3) ShowStep(_step - 1); };

            _nextBtn = new Button
            {
                Text = "Continue →",
                Width = 124,
                Height = 34,
                Location = new Point(474, 14),
                FlatStyle = FlatStyle.Flat,
                ForeColor = Color.FromArgb(17, 17, 18),
                BackColor = TextPrimary,
                Font = new Font("Segoe UI", 9f, FontStyle.Bold)
            };
            _nextBtn.FlatAppearance.BorderColor = SilverAccent;
            _nextBtn.Click += OnNextClicked;

            footer.Controls.Add(_cancelBtn);
            footer.Controls.Add(_backBtn);
            footer.Controls.Add(_nextBtn);

            _contentPanel = new Panel { Dock = DockStyle.Fill, BackColor = BgDeep, Padding = new Padding(28, 22, 28, 18) };

            Panel rightContainer = new Panel { Dock = DockStyle.Fill, BackColor = BgDeep };
            rightContainer.Controls.Add(_contentPanel);
            rightContainer.Controls.Add(footer);

            Controls.Add(rightContainer);
            Controls.Add(_sidebarPanel);
            Controls.Add(titleBar);
        }

        private void InitializeCustomizationControls(string defaultDir)
        {
            string defaultData = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "QORE", "data");
            _dirBox = StyledTextBox(defaultDir, 420);
            _dataDirBox = StyledTextBox(defaultData, 420);

            _chkAiModel = new CheckBox { Text = "Include trained RL/DL Quantum AI Model (qore-quantum-rl-dl-v1, ~32 MB)", Checked = true, AutoSize = true, ForeColor = TextPrimary, UseMnemonic = false };
            _chkDesktop = new CheckBox { Text = "Create Desktop shortcut (QORE.lnk)", Checked = true, AutoSize = true, ForeColor = TextPrimary, UseMnemonic = false };
            _chkStartMenu = new CheckBox { Text = "Create Start Menu folder and Uninstaller shortcut", Checked = true, AutoSize = true, ForeColor = TextPrimary, UseMnemonic = false };
            _chkUninstaller = new CheckBox { Text = "Register QORE in Windows Apps & Features (HKCU)", Checked = true, AutoSize = true, ForeColor = TextPrimary, UseMnemonic = false };

            _comboLaunchMode = StyledCombo(new string[] { "Standalone App Window (Edge)", "Default System Browser" }, 0, 272);
            _comboSimMethod = StyledCombo(new string[] { "statevector", "matrix_product_state", "stabilizer" }, 0, 272);
            _comboShots = StyledCombo(new string[] { "512", "1024", "2048", "4096" }, 1, 130);
            _comboForgeLevel = StyledCombo(new string[] { "0", "1", "2", "3" }, 2, 130);

            _progressBar = new GraphiteProgressBar { Width = 540, Height = 12 };
            _progressPct = new Label { Text = "0%", AutoSize = true, ForeColor = SilverAccent, Font = new Font("Consolas", 9.5f, FontStyle.Bold) };
            _statusTitle = new Label { AutoSize = true, Font = new Font("Segoe UI", 14f, FontStyle.Bold), ForeColor = TextPrimary };
            _logBox = new TextBox
            {
                Multiline = true,
                ReadOnly = true,
                ScrollBars = ScrollBars.Vertical,
                Width = 540,
                Height = 205,
                BackColor = BgSurface,
                ForeColor = TextSecondary,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Consolas", 8.5f)
            };
            _chkLaunchNow = new CheckBox { Text = "Launch QORE Desktop immediately when setup finishes", Checked = true, AutoSize = true, ForeColor = TextPrimary };
        }

        private TextBox StyledTextBox(string text, int width)
        {
            return new TextBox
            {
                Text = text,
                Width = width,
                BackColor = BgSurface,
                ForeColor = TextPrimary,
                BorderStyle = BorderStyle.FixedSingle,
                Font = new Font("Consolas", 9f)
            };
        }

        private ComboBox StyledCombo(string[] items, int selectedIndex, int width)
        {
            ComboBox cb = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDownList,
                DrawMode = DrawMode.OwnerDrawFixed,
                ItemHeight = 20,
                Width = width,
                BackColor = BgSurface,
                ForeColor = TextPrimary,
                FlatStyle = FlatStyle.Flat,
                Font = new Font("Consolas", 9f)
            };
            cb.DrawItem += delegate(object sender, DrawItemEventArgs e)
            {
                if (e.Index < 0) return;
                bool selected = (e.State & DrawItemState.Selected) == DrawItemState.Selected;
                Color bg = selected ? BgCard : BgSurface;
                using (SolidBrush b = new SolidBrush(bg)) e.Graphics.FillRectangle(b, e.Bounds);
                string text = cb.Items[e.Index].ToString();
                TextRenderer.DrawText(e.Graphics, text, cb.Font, new Rectangle(e.Bounds.X + 4, e.Bounds.Y + 2, e.Bounds.Width - 6, e.Bounds.Height - 2), TextPrimary, TextFormatFlags.Left | TextFormatFlags.VerticalCenter | TextFormatFlags.EndEllipsis);
            };
            cb.Items.AddRange(items);
            cb.SelectedIndex = selectedIndex;
            return cb;
        }

        private Panel CreateCard(int x, int y, int w, int h, string kickerText)
        {
            Panel card = new Panel { Location = new Point(x, y), Size = new Size(w, h), BackColor = BgPanel };
            card.Paint += delegate(object s, PaintEventArgs e)
            {
                using (Pen p = new Pen(BorderSubtle)) e.Graphics.DrawRectangle(p, 0, 0, card.Width - 1, card.Height - 1);
            };
            if (!string.IsNullOrEmpty(kickerText))
            {
                card.Controls.Add(new Label
                {
                    Text = kickerText,
                    ForeColor = TextMuted,
                    Font = new Font("Consolas", 7.8f, FontStyle.Bold),
                    Location = new Point(16, 12),
                    AutoSize = true,
                    UseMnemonic = false
                });
            }
            return card;
        }

        private void UpdateSidebar(int activeStep)
        {
            for (int i = 0; i < 5; i++)
            {
                if (i < activeStep)
                {
                    _stepBadges[i].Text = "✓";
                    _stepBadges[i].BackColor = Color.FromArgb(44, 62, 50);
                    _stepBadges[i].ForeColor = OkGreen;
                    _stepLabels[i].ForeColor = TextSecondary;
                    _stepLabels[i].Font = new Font("Segoe UI", 9f);
                }
                else if (i == activeStep)
                {
                    _stepBadges[i].Text = "0" + (i + 1);
                    _stepBadges[i].BackColor = TextPrimary;
                    _stepBadges[i].ForeColor = BgDeep;
                    _stepLabels[i].ForeColor = TextPrimary;
                    _stepLabels[i].Font = new Font("Segoe UI", 9f, FontStyle.Bold);
                }
                else
                {
                    _stepBadges[i].Text = "0" + (i + 1);
                    _stepBadges[i].BackColor = BgPanel;
                    _stepBadges[i].ForeColor = TextMuted;
                    _stepLabels[i].ForeColor = TextMuted;
                    _stepLabels[i].Font = new Font("Segoe UI", 9f);
                }
            }
        }

        public void ShowStep(int step)
        {
            _step = step;
            UpdateSidebar(step);
            _contentPanel.Controls.Clear();

            if (step == 0)
            {
                string py = Program.ResolvePythonPath(_sourceRoot);
                bool hasAi = File.Exists(Path.Combine(_sourceRoot, "backend", "qore", "qore_ai_model.joblib"));
                bool hasDist = Directory.Exists(Path.Combine(_sourceRoot, "frontend", "dist"));
                bool hasEdge = Program.HasEdgeDesktopHost();

                _contentPanel.Controls.Add(new Label { Text = "01 · WELCOME & PREFLIGHT", ForeColor = TextMuted, Font = new Font("Consolas", 8f, FontStyle.Bold), Location = new Point(28, 22), AutoSize = true, UseMnemonic = false });
                _contentPanel.Controls.Add(new Label { Text = "Install QORE Desktop", ForeColor = TextPrimary, Font = new Font("Segoe UI", 18f, FontStyle.Bold), Location = new Point(26, 42), AutoSize = true, UseMnemonic = false });
                _contentPanel.Controls.Add(new Label
                {
                    Text = "Configure your local quantum workstation with Studio, Qiskit Aer Lab, Forge equivalence checks, SQLite Ledger, and the trained RL/DL QORE Intelligence model.",
                    ForeColor = TextSecondary,
                    Location = new Point(28, 82),
                    Size = new Size(540, 42),
                    UseMnemonic = false
                });

                Panel card = CreateCard(28, 138, 540, 232, "SYSTEM PREFLIGHT DIAGNOSTICS");
                AddStatusRow(card, 44, "Python & Qiskit Runtime", !string.IsNullOrEmpty(py), !string.IsNullOrEmpty(py) ? py : "Not detected (requires Python 3.11+ & Qiskit)");
                AddStatusRow(card, 88, "Built-in AI Weights", hasAi, hasAi ? "Ready — qore-quantum-rl-dl-v1 (DeepMLP + IBM RL)" : "Will initialize on first launch");
                AddStatusRow(card, 132, "Graphite Web Bundle", hasDist, hasDist ? "Verified — frontend/dist compiled" : "Missing frontend/dist payload");
                AddStatusRow(card, 176, "Desktop App Host", hasEdge, hasEdge ? "Microsoft Edge App Mode available" : "Fallback to default system browser");
                _contentPanel.Controls.Add(card);

                _backBtn.Visible = false;
                _cancelBtn.Visible = true;
                _cancelBtn.Enabled = true;
                _nextBtn.Text = "Customize →";
                _nextBtn.Enabled = hasDist;
            }
            else if (step == 1)
            {
                _contentPanel.Controls.Add(new Label { Text = "02 · LOCATION & AI MODEL", ForeColor = TextMuted, Font = new Font("Consolas", 8f, FontStyle.Bold), Location = new Point(28, 22), AutoSize = true, UseMnemonic = false });
                _contentPanel.Controls.Add(new Label { Text = "Install Path & Components", ForeColor = TextPrimary, Font = new Font("Segoe UI", 17f, FontStyle.Bold), Location = new Point(26, 42), AutoSize = true, UseMnemonic = false });

                Panel locCard = CreateCard(28, 86, 540, 152, "APPLICATION & DATA DIRECTORIES");
                locCard.Controls.Add(new Label { Text = "Program Destination Folder:", ForeColor = TextSecondary, Location = new Point(16, 36), AutoSize = true, Font = new Font("Segoe UI", 8.5f, FontStyle.Bold), UseMnemonic = false });
                _dirBox.Location = new Point(16, 58);
                Button browseApp = new Button { Text = "Browse…", Location = new Point(444, 56), Width = 80, Height = 24, FlatStyle = FlatStyle.Flat, BackColor = BgCard, ForeColor = TextPrimary };
                browseApp.FlatAppearance.BorderColor = BorderSubtle;
                browseApp.Click += delegate
                {
                    using (FolderBrowserDialog fbd = new FolderBrowserDialog())
                    {
                        fbd.SelectedPath = _dirBox.Text;
                        if (fbd.ShowDialog() == DialogResult.OK) _dirBox.Text = fbd.SelectedPath;
                    }
                };
                locCard.Controls.Add(_dirBox);
                locCard.Controls.Add(browseApp);

                locCard.Controls.Add(new Label { Text = "SQLite Ledger & Workspace Data Folder:", ForeColor = TextSecondary, Location = new Point(16, 92), AutoSize = true, Font = new Font("Segoe UI", 8.5f, FontStyle.Bold), UseMnemonic = false });
                _dataDirBox.Location = new Point(16, 114);
                Button browseData = new Button { Text = "Browse…", Location = new Point(444, 112), Width = 80, Height = 24, FlatStyle = FlatStyle.Flat, BackColor = BgCard, ForeColor = TextPrimary };
                browseData.FlatAppearance.BorderColor = BorderSubtle;
                browseData.Click += delegate
                {
                    using (FolderBrowserDialog fbd = new FolderBrowserDialog())
                    {
                        fbd.SelectedPath = _dataDirBox.Text;
                        if (fbd.ShowDialog() == DialogResult.OK) _dataDirBox.Text = fbd.SelectedPath;
                    }
                };
                locCard.Controls.Add(_dataDirBox);
                locCard.Controls.Add(browseData);

                Panel compCard = CreateCard(28, 252, 540, 128, "WORKBENCH & AI COMPONENTS");
                compCard.Controls.Add(new Label
                {
                    Text = "✓  QORE Core Workbench (Studio, Quantum Lab, Forge, Research Ledger) — Required",
                    ForeColor = OkGreen,
                    Location = new Point(16, 40),
                    AutoSize = true,
                    UseMnemonic = false
                });
                _chkAiModel.Location = new Point(16, 70);
                compCard.Controls.Add(_chkAiModel);
                compCard.Controls.Add(new Label
                {
                    Text = "All circuits & AI inference stay local on this PC unless optional GEMINI_API_KEY is set.",
                    ForeColor = TextMuted,
                    Font = new Font("Segoe UI", 8.2f),
                    Location = new Point(36, 96),
                    AutoSize = true,
                    UseMnemonic = false
                });

                _contentPanel.Controls.Add(locCard);
                _contentPanel.Controls.Add(compCard);

                _backBtn.Visible = true;
                _backBtn.Enabled = true;
                _cancelBtn.Visible = true;
                _cancelBtn.Enabled = true;
                _nextBtn.Text = "Next →";
                _nextBtn.Enabled = true;
            }
            else if (step == 2)
            {
                _contentPanel.Controls.Add(new Label { Text = "03 · RUNTIME & SHORTCUTS", ForeColor = TextMuted, Font = new Font("Consolas", 8f, FontStyle.Bold), Location = new Point(28, 22), AutoSize = true, UseMnemonic = false });
                _contentPanel.Controls.Add(new Label { Text = "Customize Defaults & Integration", ForeColor = TextPrimary, Font = new Font("Segoe UI", 17f, FontStyle.Bold), Location = new Point(26, 42), AutoSize = true, UseMnemonic = false });

                Panel rtCard = CreateCard(28, 86, 540, 152, "QUANTUM RUNTIME & WINDOW DEFAULTS");
                rtCard.Controls.Add(new Label { Text = "Desktop Window Mode:", ForeColor = TextSecondary, Location = new Point(16, 42), AutoSize = true, UseMnemonic = false });
                _comboLaunchMode.Location = new Point(244, 38);
                rtCard.Controls.Add(_comboLaunchMode);

                rtCard.Controls.Add(new Label { Text = "Default Aer Simulator:", ForeColor = TextSecondary, Location = new Point(16, 78), AutoSize = true, UseMnemonic = false });
                _comboSimMethod.Location = new Point(244, 74);
                rtCard.Controls.Add(_comboSimMethod);

                rtCard.Controls.Add(new Label { Text = "Default Shots / Forge Level:", ForeColor = TextSecondary, Location = new Point(16, 114), AutoSize = true, UseMnemonic = false });
                _comboShots.Location = new Point(244, 110);
                _comboForgeLevel.Location = new Point(386, 110);
                rtCard.Controls.Add(_comboShots);
                rtCard.Controls.Add(_comboForgeLevel);

                Panel intCard = CreateCard(28, 252, 540, 132, "WINDOWS DESKTOP INTEGRATION");
                _chkDesktop.Location = new Point(16, 38);
                _chkStartMenu.Location = new Point(16, 66);
                _chkUninstaller.Location = new Point(16, 94);
                intCard.Controls.Add(_chkDesktop);
                intCard.Controls.Add(_chkStartMenu);
                intCard.Controls.Add(_chkUninstaller);

                _contentPanel.Controls.Add(rtCard);
                _contentPanel.Controls.Add(intCard);

                _backBtn.Visible = true;
                _backBtn.Enabled = true;
                _cancelBtn.Visible = true;
                _cancelBtn.Enabled = true;
                _nextBtn.Text = "Install QORE";
                _nextBtn.Enabled = true;
            }
            else if (step == 3)
            {
                _contentPanel.Controls.Add(new Label { Text = "04 · INSTALLING", ForeColor = TextMuted, Font = new Font("Consolas", 8f, FontStyle.Bold), Location = new Point(28, 22), AutoSize = true, UseMnemonic = false });
                _statusTitle.Text = "Installing QORE Desktop…";
                _statusTitle.Location = new Point(26, 44);
                _progressBar.Location = new Point(28, 92);
                _progressBar.Value = 0;
                _progressPct.Location = new Point(526, 68);
                _progressPct.Text = "0%";
                _logBox.Location = new Point(28, 120);
                _logBox.Clear();

                _contentPanel.Controls.Add(_statusTitle);
                _contentPanel.Controls.Add(_progressPct);
                _contentPanel.Controls.Add(_progressBar);
                _contentPanel.Controls.Add(_logBox);

                _backBtn.Visible = false;
                _cancelBtn.Visible = false;
                _nextBtn.Text = "Installing…";
                _nextBtn.Enabled = false;
                RunAsyncInstall();
            }
            else if (step == 4)
            {
                _contentPanel.Controls.Add(new Label { Text = "05 · COMPLETE", ForeColor = OkGreen, Font = new Font("Consolas", 8f, FontStyle.Bold), Location = new Point(28, 22), AutoSize = true, UseMnemonic = false });
                _statusTitle.Text = "QORE Desktop is Ready";
                _statusTitle.Location = new Point(26, 44);

                Panel doneCard = CreateCard(28, 92, 540, 196, "INSTALLATION SUMMARY");
                string summaryText =
                    "Application Folder : " + _dirBox.Text.Trim() + "\n" +
                    "SQLite Ledger Data : " + _dataDirBox.Text.Trim() + "\n" +
                    "Quantum AI Model   : " + (_chkAiModel.Checked ? "qore-quantum-rl-dl-v1 (Installed)" : "Disabled") + "\n" +
                    "Window Host Mode   : " + (_comboLaunchMode.SelectedIndex == 0 ? "Standalone App Window" : "Default Browser") + "\n" +
                    "Simulator / Forge  : " + _comboSimMethod.Text + " · " + _comboShots.Text + " shots · Level " + _comboForgeLevel.Text;
                doneCard.Controls.Add(new Label
                {
                    Text = summaryText,
                    ForeColor = TextSecondary,
                    Font = new Font("Consolas", 8.6f),
                    Location = new Point(16, 40),
                    Size = new Size(508, 138),
                    UseMnemonic = false
                });

                _chkLaunchNow.Location = new Point(28, 308);
                _contentPanel.Controls.Add(_statusTitle);
                _contentPanel.Controls.Add(doneCard);
                _contentPanel.Controls.Add(_chkLaunchNow);

                _backBtn.Visible = false;
                _cancelBtn.Visible = false;
                _nextBtn.Text = "Finish";
                _nextBtn.Enabled = true;
            }
        }

        private void AddStatusRow(Panel parent, int y, string title, bool ok, string detail)
        {
            Label icon = new Label
            {
                Text = ok ? "●" : "○",
                ForeColor = ok ? OkGreen : WarnAmber,
                Location = new Point(16, y),
                AutoSize = true,
                Font = new Font("Segoe UI", 10f)
            };
            Label lbl = new Label
            {
                Text = title,
                ForeColor = TextPrimary,
                Location = new Point(36, y + 1),
                AutoSize = true,
                Font = new Font("Segoe UI", 9f, FontStyle.Bold),
                UseMnemonic = false
            };
            Label det = new Label
            {
                Text = detail,
                ForeColor = TextMuted,
                Location = new Point(36, y + 20),
                Size = new Size(490, 18),
                Font = new Font("Consolas", 8f),
                UseMnemonic = false
            };
            parent.Controls.Add(icon);
            parent.Controls.Add(lbl);
            parent.Controls.Add(det);
        }

        private void OnNextClicked(object sender, EventArgs e)
        {
            if (_step < 3) ShowStep(_step + 1);
            else if (_step == 4)
            {
                if (_chkLaunchNow.Checked)
                {
                    string exe = Path.Combine(_dirBox.Text.Trim(), "QORE-Desktop.exe");
                    if (File.Exists(exe)) Process.Start(new ProcessStartInfo(exe) { WorkingDirectory = _dirBox.Text.Trim(), UseShellExecute = true });
                }
                Close();
            }
        }

        private void RunAsyncInstall()
        {
            Program.InstallOptions opts = new Program.InstallOptions
            {
                SourceRoot = _sourceRoot,
                TargetDir = _dirBox.Text.Trim(),
                DataDir = _dataDirBox.Text.Trim(),
                IncludeAiModel = _chkAiModel.Checked,
                CreateDesktopShortcut = _chkDesktop.Checked,
                CreateStartMenuShortcut = _chkStartMenu.Checked,
                RegisterUninstaller = _chkUninstaller.Checked,
                LaunchMode = _comboLaunchMode.SelectedIndex == 0 ? "app" : "browser",
                SimMethod = _comboSimMethod.Text,
                DefaultShots = _comboShots.Text,
                ForgeLevel = _comboForgeLevel.Text
            };

            Thread t = new Thread(delegate()
            {
                string err = Program.PerformInstall(opts, delegate(int pct, string msg)
                {
                    BeginInvoke((Action)delegate
                    {
                        _progressBar.Value = Math.Min(100, Math.Max(0, pct));
                        _progressPct.Text = pct + "%";
                        _logBox.AppendText(msg + Environment.NewLine);
                    });
                });

                BeginInvoke((Action)delegate
                {
                    if (!string.IsNullOrEmpty(err))
                    {
                        _statusTitle.Text = "Installation Failed";
                        _logBox.AppendText("ERROR: " + err + Environment.NewLine);
                        _cancelBtn.Enabled = true;
                    }
                    else
                    {
                        ShowStep(4);
                    }
                });
            });
            t.IsBackground = true;
            t.Start();
        }

        public void ExportPreviewScreenshots(string outDir)
        {
            Directory.CreateDirectory(outDir);
            Show();
            for (int step = 0; step <= 4; step++)
            {
                if (step == 3)
                {
                    _step = 3;
                    UpdateSidebar(3);
                    _contentPanel.Controls.Clear();
                    _contentPanel.Controls.Add(new Label { Text = "04 · INSTALLING", ForeColor = TextMuted, Font = new Font("Consolas", 8f, FontStyle.Bold), Location = new Point(28, 22), AutoSize = true, UseMnemonic = false });
                    _statusTitle.Text = "Installing QORE Desktop…";
                    _statusTitle.Location = new Point(26, 44);
                    _progressBar.Location = new Point(28, 92);
                    _progressBar.Value = 68;
                    _progressPct.Location = new Point(526, 68);
                    _progressPct.Text = "68%";
                    _logBox.Location = new Point(28, 120);
                    _logBox.Text = "Validating QORE payload...\r\nCopying QORE-Desktop.exe host launcher...\r\nInstalling QORE backend engine, Qiskit IR & Forge...\r\nInstalling Graphite Studio/Lab/Forge frontend bundle...\r\n";
                    _contentPanel.Controls.Add(_statusTitle);
                    _contentPanel.Controls.Add(_progressPct);
                    _contentPanel.Controls.Add(_progressBar);
                    _contentPanel.Controls.Add(_logBox);
                    _backBtn.Visible = false;
                    _cancelBtn.Visible = false;
                    _nextBtn.Text = "Installing…";
                    _nextBtn.Enabled = false;
                }
                else
                {
                    ShowStep(step);
                }
                Application.DoEvents();
                using (Bitmap bmp = new Bitmap(Width, Height))
                {
                    DrawToBitmap(bmp, new Rectangle(0, 0, Width, Height));
                    bmp.Save(Path.Combine(outDir, "installer_step_" + (step + 1) + ".png"), ImageFormat.Png);
                }
            }
            Hide();
        }
    }
}
