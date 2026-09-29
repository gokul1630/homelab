const http = require("http");

const port = process.env.PORT || 3000;
const version = process.env.APP_VERSION || "1.0.0";

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ status: "healthy" }));
  }

  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({
    message: "Hello from ECS Fargate test",
    version,
    hostname: require("os").hostname()
  }));
});

server.listen(port, "0.0.0.0", () => {
  console.log(`Application listening on port ${port}`);
});