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
    public async Task<IActionResult> Analyze(IFormFile file)
    {
        _logger.LogInformation("POST /bankstatement/analyze requested");

        if (file == null || file.Length == 0)
        {
            _logger.LogWarning("No file uploaded in request");
            return BadRequest("No file uploaded");
        }

        _logger.LogInformation("Received file: {FileName}, size={Size} bytes, contentType={ContentType}",
            file.FileName, file.Length, file.ContentType);

        if (file.ContentType != "application/pdf")
        {
            _logger.LogWarning("Rejected non-PDF file: contentType={ContentType}", file.ContentType);
            return BadRequest("Only PDF files are accepted");
        }

        var client = _httpClientFactory.CreateClient("AiService");

        using var content = new MultipartFormDataContent();
        using var stream = file.OpenReadStream();
        var streamContent = new StreamContent(stream);
        streamContent.Headers.ContentType = new System.Net.Http.Headers.MediaTypeHeaderValue(file.ContentType);
        content.Add(streamContent, "file", file.FileName);

        _logger.LogInformation("Forwarding PDF to AI service at /bank-statement/analyze");
        var response = await client.PostAsync("/bank-statement/analyze", content);

        if (!response.IsSuccessStatusCode)
        {
            var error = await response.Content.ReadAsStringAsync();
            _logger.LogError("AI service error: {StatusCode} - {Error}", response.StatusCode, error);
            return StatusCode((int)response.StatusCode, error);
        }

        _logger.LogInformation("AI service returned success for bank statement analysis");
        var result = await response.Content.ReadAsStringAsync();
        return Content(result, "application/json");
    }
}
