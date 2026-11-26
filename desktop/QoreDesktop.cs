// QORE Desktop Host Application (C# 5 / .NET Framework 4.x compatible)
// Reads qore-desktop.json customizations (python_executable, data_dir, launch_mode),
// starts local FastAPI + Qiskit + RL/DL AI server on a free loopback port,
// shows a Graphite splash screen, and launches QORE in standalone App Mode or browser.

using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using System.Windows.Forms;

[assembly: AssemblyTitle("QORE Desktop")]
[assembly: AssemblyDescription("QORE Quantum Development Desktop Host")]
[assembly: AssemblyCompany("QORE")]
[assembly: AssemblyProduct("QORE Desktop")]
[assembly: AssemblyVersion("0.1.0.0")]
[assembly: AssemblyFileVersion("0.1.0.0")]

namespace QoreDesktop
{
    static class Program
    {
        private static Process _backendProcess;
        private static readonly object _sync = new object();

        [STAThread]
        static int Main(string[] args)
        {
            bool headlessCheck = false;
            for (int i = 0; i < args.Length; i++)
            {
                if (string.Equals(args[i], "--headless-check", StringComparison.OrdinalIgnoreCase))
                {
                    headlessCheck = true;
                }
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
            string probe = baseDir;
            for (int depth = 0; depth < 3; depth++)
            {
                if (Directory.Exists(Path.Combine(probe, "backend")))
                {
                    baseDir = probe;
                    break;
                }
                DirectoryInfo parentInfo = Directory.GetParent(probe);
                if (parentInfo == null) break;
                probe = parentInfo.FullName;
            }

            string cfgText = ReadConfigText(baseDir);
            string pythonExe = ResolvePython(baseDir, cfgText);
            string backendDir = Path.Combine(baseDir, "backend");

            if (string.IsNullOrEmpty(pythonExe) || !File.Exists(pythonExe))
            {
                string msg = "QORE could not locate a Python runtime with Qiskit and FastAPI installed.\n\n" +
                             "Expected .venv\\Scripts\\python.exe, qore-desktop.json, or QORE_PYTHON.";
                if (headlessCheck) Console.Error.WriteLine(msg);
                else MessageBox.Show(msg, "QORE Desktop — Runtime Missing", MessageBoxButtons.OK, MessageBoxIcon.Error);
                return 2;
            }

            int port = AllocateFreePort();
            string customDataDir = ReadJsonString(cfgText, "data_dir");
            string dataDir = !string.IsNullOrEmpty(customDataDir)
                ? customDataDir
                : Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "QORE", "data");
            Directory.CreateDirectory(dataDir);
            string dbPath = Path.Combine(dataDir, "qore.sqlite3");

            string launchMode = ReadJsonString(cfgText, "launch_mode");
            if (string.IsNullOrEmpty(launchMode)) launchMode = "app";

            if (!StartBackend(pythonExe, baseDir, backendDir, dbPath, port))
            {
                string err = "QORE backend failed to start on 127.0.0.1:" + port;
                if (headlessCheck) Console.Error.WriteLine(err);
                else MessageBox.Show(err, "QORE Desktop — Startup Error", MessageBoxButtons.OK, MessageBoxIcon.Error);
                StopBackend();
                return 3;
            }

            string healthUrl = string.Format("http://127.0.0.1:{0}/api/health", port);
            string appUrl = string.Format("http://127.0.0.1:{0}/", port);

            if (headlessCheck)
            {
                string healthJson = WaitForHealth(healthUrl, 30000);
                StopBackend();
                if (string.IsNullOrEmpty(healthJson))
                {
                    Console.Error.WriteLine("QORE backend health check timed out.");
                    return 4;
                }
                Console.WriteLine(healthJson);
                return 0;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);

            Form splash = CreateSplashForm();
            splash.Show();
            Application.DoEvents();

            string readyJson = null;
            Thread waitThread = new Thread(delegate()
            {
                readyJson = WaitForHealth(healthUrl, 35000);
            });
            waitThread.IsBackground = true;
            waitThread.Start();

            while (waitThread.IsAlive)
            {
                Application.DoEvents();
                Thread.Sleep(50);
            }

            splash.Close();
            splash.Dispose();

            if (string.IsNullOrEmpty(readyJson))
            {
                StopBackend();
                MessageBox.Show(
                    "QORE Desktop timed out waiting for the local Quantum Runtime & RL/DL AI server.",
                    "QORE Desktop — Startup Timeout",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Error
                );
                return 5;
            }

            try
            {
                LaunchDesktopWindow(appUrl, launchMode);
            }
            finally
            {
                StopBackend();
            }
            return 0;
        }

        private static string ReadConfigText(string baseDir)
        {
            string cfgPath = Path.Combine(baseDir, "qore-desktop.json");
            if (!File.Exists(cfgPath))
            {
                string exeCfg = Path.Combine(AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\'), "qore-desktop.json");
                if (File.Exists(exeCfg)) cfgPath = exeCfg;
                else return "";
            }
            try { return File.ReadAllText(cfgPath, Encoding.UTF8); }
            catch { return ""; }
        }

        private static string ReadJsonString(string raw, string key)
        {
            if (string.IsNullOrEmpty(raw)) return "";
            string marker = "\"" + key + "\"";
            int idx = raw.IndexOf(marker, StringComparison.OrdinalIgnoreCase);
            if (idx < 0) return "";
            int colon = raw.IndexOf(':', idx + marker.Length);
            if (colon < 0) return "";
            int q1 = raw.IndexOf('"', colon + 1);
            if (q1 < 0) return "";
            int q2 = q1 + 1;
            while (q2 < raw.Length)
            {
                if (raw[q2] == '"' && raw[q2 - 1] != '\\') break;
                q2++;
            }
            if (q2 >= raw.Length) return "";
            return raw.Substring(q1 + 1, q2 - q1 - 1).Replace("\\\\", "\\");
        }

        private static string ResolvePython(string baseDir, string cfgText)
        {
            string envPy = Environment.GetEnvironmentVariable("QORE_PYTHON");
            if (!string.IsNullOrEmpty(envPy) && File.Exists(envPy)) return envPy;

            string configuredPy = ReadJsonString(cfgText, "python_executable");
            if (!string.IsNullOrEmpty(configuredPy) && File.Exists(configuredPy)) return configuredPy;

            string[] candidates = new string[]
            {
                Path.Combine(baseDir, ".venv", "Scripts", "python.exe"),
                Path.Combine(baseDir, "runtime", "python.exe"),
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
            return null;
        }

        private static int AllocateFreePort()
        {
            TcpListener listener = new TcpListener(IPAddress.Loopback, 0);
            listener.Start();
            int port = ((IPEndPoint)listener.LocalEndpoint).Port;
            listener.Stop();
            return port;
        }

        private static bool StartBackend(string pythonExe, string baseDir, string backendDir, string dbPath, int port)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo();
                psi.FileName = pythonExe;
                psi.Arguments = string.Format("-m uvicorn qore.main:app --host 127.0.0.1 --port {0}", port);
                psi.WorkingDirectory = baseDir;
                psi.UseShellExecute = false;
                psi.CreateNoWindow = true;
                psi.WindowStyle = ProcessWindowStyle.Hidden;
                psi.EnvironmentVariables["PYTHONPATH"] = backendDir;
                psi.EnvironmentVariables["QORE_STORAGE"] = "sqlite";
                psi.EnvironmentVariables["QORE_DB_PATH"] = dbPath;
                psi.EnvironmentVariables["QORE_PUBLIC_URL"] = string.Format("http://127.0.0.1:{0}", port);

                lock (_sync)
                {
                    _backendProcess = Process.Start(psi);
                    return _backendProcess != null;
                }
            }
            catch
            {
                return false;
            }
        }

        private static void StopBackend()
        {
            lock (_sync)
            {
                if (_backendProcess != null)
                {
                    try
                    {
                        if (!_backendProcess.HasExited)
                        {
                            Process.Start(new ProcessStartInfo
                            {
                                FileName = "taskkill",
                                Arguments = string.Format("/PID {0} /T /F", _backendProcess.Id),
                                UseShellExecute = false,
                                CreateNoWindow = true
                            }).WaitForExit(3000);
                        }
                    }
                    catch { }
                    finally
                    {
                        _backendProcess.Dispose();
                        _backendProcess = null;
                    }
                }
            }
        }

        private static string WaitForHealth(string healthUrl, int timeoutMs)
        {
            Stopwatch sw = Stopwatch.StartNew();
            while (sw.ElapsedMilliseconds < timeoutMs)
            {
                lock (_sync)
                {
                    if (_backendProcess != null && _backendProcess.HasExited) return null;
                }
                try
                {
                    HttpWebRequest req = (HttpWebRequest)WebRequest.Create(healthUrl);
                    req.Timeout = 1500;
                    using (HttpWebResponse resp = (HttpWebResponse)req.GetResponse())
                    {
                        if (resp.StatusCode == HttpStatusCode.OK)
                        {
                            using (StreamReader sr = new StreamReader(resp.GetResponseStream(), Encoding.UTF8))
                            {
                                return sr.ReadToEnd();
                            }
                        }
                    }
                }
                catch
                {
                    Thread.Sleep(200);
                }
            }
            return null;
        }

        private static void LaunchDesktopWindow(string appUrl, string launchMode)
        {
            if (!string.Equals(launchMode, "browser", StringComparison.OrdinalIgnoreCase))
            {
                string appHostPath = FindAppHostExecutable();
                if (!string.IsNullOrEmpty(appHostPath))
                {
                    string profileDir = Path.Combine(
                        Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
                        "QORE",
                        "desktop-profile"
                    );
                    Directory.CreateDirectory(profileDir);

                    ProcessStartInfo psi = new ProcessStartInfo();
                    psi.FileName = appHostPath;
                    psi.Arguments = string.Format(
                        "--app=\"{0}\" --new-window --user-data-dir=\"{1}\" --window-size=1440,920 --no-first-run --disable-features=msEdgeSidebarV2",
                        appUrl,
                        profileDir
                    );
                    psi.UseShellExecute = false;
                    using (Process uiProc = Process.Start(psi))
                    {
                        if (uiProc != null)
                        {
                            uiProc.WaitForExit();
                            return;
                        }
                    }
                }
            }

            Process.Start(new ProcessStartInfo(appUrl) { UseShellExecute = true });
            MessageBox.Show(
                "QORE Desktop is running at " + appUrl + "\n\nClick OK to stop the local QORE runtime when finished.",
                "QORE Desktop Server Active",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information
            );
        }

        private static string FindAppHostExecutable()
        {
            string localApp = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            string[] candidates = new string[]
            {
                @"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                @"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                Path.Combine(localApp, @"Microsoft\Edge\Application\msedge.exe"),
                @"C:\Program Files\Google\Chrome\Application\chrome.exe",
                @"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                Path.Combine(localApp, @"Google\Chrome\Application\chrome.exe")
            };
            for (int i = 0; i < candidates.Length; i++)
            {
                if (File.Exists(candidates[i])) return candidates[i];
            }
            return null;
        }

        private static Form CreateSplashForm()
        {
            Form f = new Form();
            f.Text = "QORE Desktop";
            f.FormBorderStyle = FormBorderStyle.None;
            f.StartPosition = FormStartPosition.CenterScreen;
            f.Size = new Size(440, 210);
            f.BackColor = Color.FromArgb(17, 17, 18);

            Panel border = new Panel();
            border.Dock = DockStyle.Fill;
            border.Padding = new Padding(24);
            border.BackColor = Color.FromArgb(17, 17, 18);

            Label badge = new Label();
            badge.Text = "QORE · THE CORE OF QUANTUM DEVELOPMENT";
            badge.ForeColor = Color.FromArgb(160, 158, 153);
            badge.Font = new Font("Segoe UI", 8.5f, FontStyle.Bold);
            badge.AutoSize = true;
            badge.Location = new Point(26, 28);

            Label title = new Label();
            title.Text = "Starting QORE Desktop";
            title.ForeColor = Color.FromArgb(244, 242, 238);
            title.Font = new Font("Segoe UI", 18f, FontStyle.Bold);
            title.AutoSize = true;
            title.Location = new Point(24, 56);

            Label sub = new Label();
            sub.Text = "Initializing Qiskit Aer Simulator, Forge Compiler, and RL/DL Quantum AI...";
            sub.ForeColor = Color.FromArgb(190, 188, 183);
            sub.Font = new Font("Segoe UI", 9.5f, FontStyle.Regular);
            sub.Size = new Size(390, 44);
            sub.Location = new Point(26, 102);

            ProgressBar bar = new ProgressBar();
            bar.Style = ProgressBarStyle.Marquee;
            bar.MarqueeAnimationSpeed = 24;
            bar.Location = new Point(26, 158);
            bar.Size = new Size(388, 14);

            border.Controls.Add(badge);
            border.Controls.Add(title);
            border.Controls.Add(sub);
            border.Controls.Add(bar);
            f.Controls.Add(border);
            return f;
        }
    }
}
