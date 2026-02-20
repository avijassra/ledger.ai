var builder = WebApplication.CreateBuilder(args);

// Add services to the container.

builder.Services.AddControllers();

builder.Services.AddHttpClient("AiService", client =>
{
    client.BaseAddress = new Uri(builder.Configuration["AiService:BaseUrl"] ?? "http://localhost:8000");
    client.Timeout = TimeSpan.FromSeconds(180);
});
// Learn more about configuring Swagger/OpenAPI at https://aka.ms/aspnetcore/swashbuckle
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

var app = builder.Build();

var logger = app.Services.GetRequiredService<ILogger<Program>>();
logger.LogInformation("LedgerAI Web API starting up");

// Configure the HTTP request pipeline.
if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI(c =>
    {
        c.SwaggerEndpoint("/swagger/v1/swagger.json", "LedgerAI API v1");
        c.RoutePrefix = string.Empty;
    });
}
else
{
    app.UseHttpsRedirection();
}

app.UseAuthorization();

app.Use(async (context, next) =>
{
    var requestLogger = context.RequestServices.GetRequiredService<ILogger<Program>>();
    requestLogger.LogInformation("Request: {Method} {Path}", context.Request.Method, context.Request.Path);
    await next();
    requestLogger.LogInformation("Response: {Method} {Path} -> {StatusCode}", context.Request.Method, context.Request.Path, context.Response.StatusCode);
});

app.MapControllers();

app.Run();
