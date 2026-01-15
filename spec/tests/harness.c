#include "../../examples/order_engine/engine.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static int is_ws(char c) {
  return c==' '||c=='\t'||c=='\r'||c=='\n';
}

static char *next_tok(char **p) {
  char *s = *p;
  while (*s && is_ws(*s)) s++;
  if (!*s) { *p = s; return NULL; }
  char *t = s;
  while (*t && !is_ws(*t)) t++;
  if (*t) *t++ = 0;
  *p = t;
  return s;
}

int main(void) {
  Engine engine;
  int inited = 0;

  // Read entire stdin into memory for speed/determinism.
  fseek(stdin, 0, SEEK_END);
  long sz = ftell(stdin);
  if (sz < 0) sz = 0;
  fseek(stdin, 0, SEEK_SET);
  char *buf = (char*)malloc((size_t)sz + 1);
  if (!buf) return 1;
  size_t got = fread(buf, 1, (size_t)sz, stdin);
  buf[got] = 0;

  char *cur = buf;
  while (*cur) {
    // get line
    char *line = cur;
    while (*cur && *cur != '\n') cur++;
    if (*cur == '\n') { *cur = 0; cur++; }

    // trim leading spaces
    while (*line && is_ws(*line)) line++;
    if (!*line) continue;

    char *p = line;
    char *cmd = next_tok(&p);
    if (!cmd) continue;

    if (strcmp(cmd, "INIT") == 0) {
      init_engine(&engine);
      inited = 1;
      fputs("OK\n", stdout);
    } else if (strcmp(cmd, "SUB") == 0) {
      char *sid = next_tok(&p);
      char *spr = next_tok(&p);
      char *sq = next_tok(&p);
      char *ss = next_tok(&p);
      if (!inited || !sid || !spr || !sq || !ss) {
        fputs("ERR\n", stdout);
        continue;
      }
      uint32_t id = (uint32_t)strtoul(sid, NULL, 10);
      uint32_t pr = (uint32_t)strtoul(spr, NULL, 10);
      uint32_t qty = (uint32_t)strtoul(sq, NULL, 10);
      Side side = (ss[0] == 'B') ? SIDE_BUY : SIDE_SELL;
      submit_order(&engine, id, pr, qty, side);
      fputs("OK\n", stdout);
    } else if (strcmp(cmd, "MAT") == 0) {
      if (!inited) { fputs("ERR\n", stdout); continue; }
      match_orders(&engine);
      fputs("OK\n", stdout);
    } else {
      fputs("ERR\n", stdout);
    }
  }

  free(buf);
  return 0;
}
