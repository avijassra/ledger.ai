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
    public async Task<IActionResult> Analyze(IFormFileCollection files)
    {
        _logger.LogInformation("POST /bankstatement/analyze requested");

        if (files == null || files.Count == 0)
        {
            _logger.LogWarning("No files uploaded in request");
            return BadRequest("No files uploaded");
        }

        _logger.LogInformation("Received {Count} file(s)", files.Count);

        var client = _httpClientFactory.CreateClient("AiService");
        var content = new MultipartFormDataContent();

        var streams = new List<Stream>();
        try
        {
            foreach (var file in files)
            {
                var isAccepted = file.ContentType == "application/pdf"
                    || file.ContentType == "text/csv"
                    || file.ContentType == "application/csv"
                    || file.ContentType == "text/plain"
                    || file.ContentType == "application/vnd.ms-excel"
                    || file.ContentType == "application/octet-stream"
                    || (file.FileName?.EndsWith(".csv", StringComparison.OrdinalIgnoreCase) ?? false)
                    || (file.FileName?.EndsWith(".pdf", StringComparison.OrdinalIgnoreCase) ?? false);

                if (!isAccepted)
                {
                    _logger.LogWarning("Rejected unsupported file: {FileName}, contentType={ContentType}", file.FileName, file.ContentType);
                    return BadRequest($"Unsupported file type for '{file.FileName}': {file.ContentType}");
                }

                _logger.LogInformation("Adding file: {FileName}, size={Size} bytes", file.FileName, file.Length);
                var stream = file.OpenReadStream();
                streams.Add(stream);
                var streamContent = new StreamContent(stream);
                streamContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(file.ContentType);
                content.Add(streamContent, "files", file.FileName ?? "upload");
            }

            _logger.LogInformation("Forwarding {Count} file(s) to AI service at /bank-statement/analyze", files.Count);
            var response = await client.PostAsync("/bank-statement/analyze", content);

            if (!response.IsSuccessStatusCode)
            {
                var error = await response.Content.ReadAsStringAsync();
                _logger.LogError("AI service error: {StatusCode} - {Error}", response.StatusCode, error);
                return StatusCode((int)response.StatusCode, error);
            }

            _logger.LogInformation("AI service returned success");
            var result = await response.Content.ReadAsStringAsync();
            return Content(result, "application/json");
        }
        finally
        {
            foreach (var stream in streams)
                stream.Dispose();
            content.Dispose();
        }
    }
}
