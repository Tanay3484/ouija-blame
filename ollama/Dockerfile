# Private Ollama server with Gemma baked in. Same as Slow Start (Week 3) and Golden Hour (Week 1), same author.
FROM ollama/ollama:0.40.2

ENV OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_KEEP_ALIVE=-1 \
    OLLAMA_CONTEXT_LENGTH=4096 \
    OLLAMA_NUM_PARALLEL=1 \
    MODEL=gemma3:4b

# Bake the model into the image so a restart never re-downloads it.
RUN (ollama serve >/dev/null 2>&1 &) \
    && until ollama list >/dev/null 2>&1; do sleep 1; done \
    && ollama pull "$MODEL"

# Inside the container llama.cpp sees the whole host, not the plan. On this plan, without these it can
# run out of memory. They sit after the model download so changing them does not re-download it.
ENV OLLAMA_MAX_LOADED_MODELS=1 \
    LLAMA_ARG_CACHE_RAM=0 \
    LLAMA_ARG_NO_REPACK=1 \
    LLAMA_ARG_THREADS=2

COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 11434
ENTRYPOINT ["/start.sh"]
