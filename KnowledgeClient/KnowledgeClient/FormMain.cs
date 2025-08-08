using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Data;
using System.Drawing;
using System.Linq;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using System.Threading.Tasks;
using System.Windows.Forms;
using System.Net.Http;
using Newtonsoft.Json.Linq;
using System.IO;
using System.Threading;



namespace KnowledgeClient
{
    public partial class FormMain : Form
    {
        private readonly HttpClient _client;
        private System.Diagnostics.Stopwatch stopwatch = new System.Diagnostics.Stopwatch();
        private System.Windows.Forms.Timer uiTimer = new System.Windows.Forms.Timer();


        public FormMain()
        {
            InitializeComponent();
            _client = new HttpClient();
            _client.Timeout = TimeSpan.FromSeconds(30 * 60);

        }

        private async void BtnSend_Click(object sender, EventArgs e)
        {
            txtResponse.Clear();
            bool bChecked = chkStream.Checked;
            BtnSend.Enabled = false;

            txtResponse.Text = "Calling API...";
            lblElapsed.Text = "Elapsed: 00:00:00";

            // Start timer and stopwatch
            stopwatch.Restart();
            uiTimer.Start();

            try
            {
                if (bChecked)
                {
                    await Response_stream();
                }
                else
                {
                    await Response();
                }
            }
            catch (Exception ex)
            {
                AppendText($"\n[Error: {ex.Message}]\n", Color.Red);
            }
            finally
            {
                // enable button
                BtnSend.Enabled = true;
                // Stop timer and stopwatch
                stopwatch.Stop();
                uiTimer.Stop();
            }

        }

        private async Task Response_stream()
        {
            string url = string.Format("{0}/api/ask_stream", txtUrl.Text);

            string json = JsonSerializer.Serialize(new { question = txtQuestion.Text });

            var request = new HttpRequestMessage(HttpMethod.Post, url)
            {
                Content = new StringContent(json, Encoding.UTF8, "application/json")
            };
            request.Headers.Add("X-API-Key", txtApiKey.Text);


            using (var response = await _client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead))
            {
                response.EnsureSuccessStatusCode();

                using (var stream = await response.Content.ReadAsStreamAsync())
                using (var reader = new System.IO.StreamReader(stream))
                {
                    string line;
                    bool bFirstLine = true;
                    while ((line = await reader.ReadLineAsync()) != null)
                    {
                        // Only parse lines starting with "data: "
                        if (line.StartsWith("data: "))
                        {
                            string data = line.Substring("data: ".Length);


                            if (data == "[DONE]")
                            {
                                AppendText($"\n{data}", Color.Red);
                                break;
                            }

                            if (!bFirstLine)
                            {
                                AppendText(data, Color.Blue);
                            }
                            else
                            {
                                bFirstLine = false;
                                AppendText($"\n{data}", Color.Blue);
                            }
                        }
                        else if (line.StartsWith("info: "))
                        {
                            string data = line.Substring("info: ".Length);
                            AppendText($"\n{data}", Color.Yellow);
                        }
                        else if (line.StartsWith("error: "))
                        {
                            string data = line.Substring("error: ".Length);
                            AppendText($"\n{data}", Color.Red);
                        }
                    }
                }
            }
        }

        private async Task Response()
        {
            string responseText = string.Empty;
            string formattedAnswer = string.Empty;
            try
            {
                string url = string.Format("{0}/api/ask", txtUrl.Text);
                string jsonBody = string.Format("{{\"question\":\"{0}\"}}", txtQuestion.Text);

                var request = new HttpRequestMessage(HttpMethod.Post, url);
                request.Headers.Add("X-API-Key", txtApiKey.Text);
                request.Content = new StringContent(jsonBody, Encoding.UTF8, "application/json");

                HttpResponseMessage response = await _client.SendAsync(request);
                response.EnsureSuccessStatusCode();

                responseText = await response.Content.ReadAsStringAsync();

                // Parse JSON and extract the "answer" value
                formattedAnswer = JObject.Parse(responseText)["answer"]?.ToString();

                // Display formatted text (newlines will now work)
                txtResponse.Text = formattedAnswer.Replace("\n", Environment.NewLine);
            }
            catch (Exception ex)
            {
                // if parse fails, try array
                JArray jsonArray = JArray.Parse(responseText);

                // check if the format matches ["answer", "content"]
                if (jsonArray.Count >= 2 && jsonArray[0]?.ToString() == "answer")
                {
                    formattedAnswer = jsonArray[1]?.ToString();
                }
                else
                {
                    formattedAnswer = "invalid response";
                }
                txtResponse.Text = formattedAnswer.Replace("\n", Environment.NewLine);
            }
        }

        // thread-safe to appent text
        private void AppendText(string text, Color color)
        {
            if (txtResponse.InvokeRequired)
            {
                txtResponse.Invoke(new Action<string, Color>(AppendText), text, color);
                return;
            }

            txtResponse.SelectionStart = txtResponse.TextLength;
            txtResponse.SelectionColor = color;
            txtResponse.AppendText(text);
            txtResponse.SelectionColor = txtResponse.ForeColor;

            // scroll to the bottom automatically
            txtResponse.ScrollToCaret();
        }



        private void FormMain_Load(object sender, EventArgs e)
        {
            txtResponse.ReadOnly = true;
            txtResponse.ScrollBars = RichTextBoxScrollBars.Vertical;
            txtResponse.WordWrap = true;


            lblElapsed.Text = string.Empty;
            uiTimer.Interval = 1000;
            uiTimer.Tick += UiTimer_Tick;
        }

        private void UiTimer_Tick(object sender, EventArgs e)
        {
            lblElapsed.Text = "Elapsed: " + stopwatch.Elapsed.ToString(@"hh\:mm\:ss");
        }
    }
}
