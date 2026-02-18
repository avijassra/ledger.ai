using Microsoft.AspNetCore.Mvc;

namespace LedgerAI.Api.Controllers;

[ApiController]
[Route("[controller]")]
public class WeatherForecastController : ControllerBase
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly ILogger<WeatherForecastController> _logger;

    public WeatherForecastController(IHttpClientFactory httpClientFactory, ILogger<WeatherForecastController> logger)
    {
        _httpClientFactory = httpClientFactory;
        _logger = logger;
    }

    [HttpGet(Name = "GetWeatherForecast")]
    public async Task<IActionResult> Get()
    {
        _logger.LogInformation("GET /weatherforecast requested");

        var client = _httpClientFactory.CreateClient("AiService");

        _logger.LogInformation("Calling AI service at /test/weather");
        var response = await client.GetAsync("/test/weather");

        if (!response.IsSuccessStatusCode)
        {
            _logger.LogError("AI service returned error: {StatusCode}", response.StatusCode);
            return StatusCode((int)response.StatusCode, "AI service error");
        }

        var forecasts = await response.Content.ReadFromJsonAsync<List<WeatherForecast>>();
        _logger.LogInformation("Weather forecast retrieved: {Count} items", forecasts?.Count ?? 0);
        return Ok(forecasts);
    }
}
