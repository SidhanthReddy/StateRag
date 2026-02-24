import express from "express";
import bodyParser from "body-parser";
import { mutate } from "./mutationEngine.js";

const app = express();
app.use(bodyParser.json({ limit: "5mb" }));

const PORT = process.env.PORT ? Number(process.env.PORT) : 3001;
const HOST = process.env.HOST || "127.0.0.1";

app.post("/mutate", async (req, res) => {
  try {
    const { code, mutation } = req.body;

    if (!code || !mutation) {
      return res.status(400).json({ error: "Missing code or mutation" });
    }

    const updated = await mutate(code, mutation);

    return res.json({ updated });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: err.message });
  }
});

app.listen(PORT, HOST, () => {
  console.log(`AST service running on http://${HOST}:${PORT}`);
});
