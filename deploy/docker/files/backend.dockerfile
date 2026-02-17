FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
WORKDIR /app

# Copy all csproj files to restore dependencies
COPY src/server/web/api/*.csproj ./api/
COPY src/server/web/application/*.csproj ./application/
COPY src/server/web/domain/*.csproj ./domain/
COPY src/server/web/infrastructure/*.csproj ./infrastructure/
COPY src/server/web/shared/*.csproj ./shared/
COPY src/server/web/LedgerAI.sln ./
RUN dotnet restore

# Copy the actual source code
COPY src/server/web/ .
RUN dotnet publish api/LedgerAI.Api.csproj -c Release -o /app/publish

FROM mcr.microsoft.com/dotnet/aspnet:8.0
WORKDIR /app
COPY --from=build /app/publish .
EXPOSE 8080
ENTRYPOINT ["dotnet", "LedgerAI.Api.dll"]
