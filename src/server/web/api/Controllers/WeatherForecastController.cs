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
        var client = _httpClientFactory.CreateClient("AiService");

        var response = await client.GetAsync("/test/weather");
        response.EnsureSuccessStatusCode();

        var forecasts = await response.Content.ReadFromJsonAsync<List<WeatherForecast>>();
        return Ok(forecasts);
    }
}
