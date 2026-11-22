/* Give ODA a fictional save-author name while retaining the real account's other properties. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <pwd.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
static const char author[] = "ZEV_OPERATOR";
struct passwd *getpwuid(uid_t uid) {
 static __thread struct passwd result;
 struct passwd *(*real_fn)(uid_t) = dlsym(RTLD_NEXT, "getpwuid");
 struct passwd *actual = real_fn(uid);
 if (!actual || uid != getuid()) return actual;
 result = *actual; result.pw_name = (char *)author; result.pw_gecos = (char *)author;
 return &result;
}
int getpwuid_r(uid_t uid, struct passwd *pwd, char *buf, size_t size, struct passwd **result) {
 int (*real_fn)(uid_t,struct passwd *,char *,size_t,struct passwd **) = dlsym(RTLD_NEXT, "getpwuid_r");
 int rc = real_fn(uid,pwd,buf,size,result);
 if (!rc && *result && uid == getuid()) { pwd->pw_name = (char *)author; pwd->pw_gecos = (char *)author; }
 return rc;
}
char *getlogin(void) { return (char *)author; }
int getlogin_r(char *buf, size_t size) {
 if (size < sizeof(author)) return ERANGE;
 memcpy(buf,author,sizeof(author)); return 0;
}
