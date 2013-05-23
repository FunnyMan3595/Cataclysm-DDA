#include "parachute.h"
#include <unistd.h>

#define DEBUGGER "gdb"

static char *_program_name = NULL;
static std::string invoke_reason = "Not set";
static int invoke_signal = -1;
static struct sigaction parachute, ignore, cleanup;

const static int signal_count = 6;
static int parachute_signals[signal_count] = {
    SIGILL,    // Illegal instruction
    SIGBUS,    // Invalid address
    SIGFPE,    // Math error
    SIGSEGV,   // Segfault
    SIGSTKFLT, // Stack fault
    SIGTRAP,   // Used by invoke_debugger
};

void setup_parachute(char *program_name)
{
    _program_name = program_name;

    sigset_t suppress;
    sigemptyset(&suppress);
    // Ignore these signals until we're done invoking the debugger.
    sigaddset(&suppress, SIGINT);  // Ctrl+C
    sigaddset(&suppress, SIGTERM); // Vanilla kill
    sigaddset(&suppress, SIGTSTP); // Ctrl+Z
    sigaddset(&suppress, SIGUSR1); // Debugger failure

    // When a parachute activates...
    // ...suppress any problematic signals...
    parachute.sa_mask = suppress;
    // ...invoke the parachute handler...
    parachute.sa_handler = parachute_handler;
    // ...and then continue where we left off.
    parachute.sa_flags = SA_RESTART;

    // Register the signal handlers.
    for (int i=0; i<signal_count; i++) {
        sigaction(parachute_signals[i], &parachute, NULL);
    }

    // Set up the "ignore it" handler, in case we need it.
    ignore.sa_mask = suppress;
    ignore.sa_handler = SIG_IGN;
    ignore.sa_flags = SA_RESTART;
    // Leave it unattached.

    // Set up the "debugger failed to run" handler.
    cleanup.sa_mask = suppress;
    cleanup.sa_handler = debugger_failed;
    cleanup.sa_flags = SA_RESTART;
    // Attach it to SIGUSR1.
    sigaction(SIGUSR1, &cleanup, NULL);
}

void invoke_debugger(std::string reason)
{
    invoke_reason = reason;
    raise(SIGTRAP);
}

void debugger_failed(int signal)
{
    // We only need to handle this once.
    // (Actually, we shouldn't ever "handle" it, since parachute_handler
    //  should call us directly.  Still, we can't ignore it before now, or it
    //  wouldn't be kept long enough for parachute_handler to see it, so this
    //  might as well be the handler until then.)
    sigaction(SIGUSR1, &ignore, NULL);

    // Ignore any SIGTRAP signals, to keep invoke_debugger from killing us.
    sigaction(SIGTRAP, &ignore, NULL);

    // parachute_handler will have already unbound 
}

void parachute_handler(int signal)
{
    invoke_signal = signal;
    if (signal != SIGTRAP) {
        invoke_reason = strsignal(signal);
    }

    int side = fork();

    if (side == 0) {
        // Child.
        pid_t cataclysm_pid = getppid();
        char pidstr[100];
        snprintf(pidstr, 100, "%d", cataclysm_pid);

        // Exec the debugger.
        execlp(DEBUGGER, DEBUGGER, _program_name, pidstr);

        // Debugger failed to start.
        // Notify and restart the parent.
        kill(cataclysm_pid, SIGUSR1);
        kill(cataclysm_pid, SIGCONT);
        // Die.
        exit(1);
    } else {
        // Parent.
        // We've invoked the debugger, so we can stop watching signals.
        for (int i=0; i<signal_count; i++) {
            // Clear the signal handler.
            sigaction(parachute_signals[i], NULL, NULL);
        }

        // Stop execution and wait for the debugger.
        raise(SIGSTOP);

        // Check to see if SIGUSR1 is pending. (i.e. the debugger didn't start)
        sigset_t pending;
        sigpending(&pending);
        if (sigismember (&pending, SIGUSR1)) {
            // Ensure we process this signal first by calling the handler
            // directly.
            debugger_failed(SIGUSR1);
        }
    }
}
