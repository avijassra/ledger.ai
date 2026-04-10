using Microsoft.AspNetCore.Mvc;

namespace LedgerAI.Api.Controllers;

[ApiController]
[Route("[controller]")]
public class BankStatementController : ControllerBase
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<BankStatementController> _logger;

    public BankStatementController(IHttpClientFactory httpClientFactory, ILogger<BankStatementController> logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
    }

    [HttpPost("analyze")]
    public async Task Analyze(IFormFileCollection files)
    {
        _logger.LogInformation("POST /bankstatement/analyze — {Count} file(s)", files?.Count ?? 0);

        if (files == null || files.Count == 0)
        {
            Response.StatusCode = 400;
            await Response.WriteAsync("No files uploaded");
            return;
        }

        var client = _httpClientFactory.CreateClient("AiService");
        var content = new MultipartFormDataContent();
        var streams = new List<Stream>();

        try
        {
            foreach (var file in files)
            {
                var stream = file.OpenReadStream();
                streams.Add(stream);
                var sc = new StreamContent(stream);
                sc.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(file.ContentType ?? "application/octet-stream");
                content.Add(sc, "files", file.FileName ?? "upload");
            }

            var request = new HttpRequestMessage(HttpMethod.Post, "/bank-statement/analyze") { Content = content };

            var aiResponse = await client.SendAsync(request, HttpCompletionOption.ResponseHeadersRead);

            if (!aiResponse.IsSuccessStatusCode)
            {
                var error = await aiResponse.Content.ReadAsStringAsync();
                _logger.LogError("AI service error: {Status} — {Error}", aiResponse.StatusCode, error);
                Response.StatusCode = (int)aiResponse.StatusCode;
                await Response.WriteAsync(error);
                return;
            }

            // Stream SSE events directly to the client
            Response.ContentType = "text/event-stream";
            Response.Headers["Cache-Control"] = "no-cache";
            Response.Headers["X-Accel-Buffering"] = "no";
            Response.Headers["Connection"] = "keep-alive";

            var aiStream = await aiResponse.Content.ReadAsStreamAsync();
            await aiStream.CopyToAsync(Response.Body);
            await Response.Body.FlushAsync();
        }
        finally
        {
            foreach (var s in streams) s.Dispose();
            content.Dispose();
        }
    }
}
