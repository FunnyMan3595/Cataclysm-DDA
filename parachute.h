#include <string>
#include <signal.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

void setup_parachute(char *program_name);
void invoke_debugger(std::string reason="Not set");
void debugger_failed(int signal);
void parachute_handler(int signal);
