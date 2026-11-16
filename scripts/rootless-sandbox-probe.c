#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <sys/stat.h>
#include <errno.h>
#include <string.h>
#include <stdlib.h>
int main(int argc,char**argv){
 if(argc>1 && strcmp(argv[1],"--spam")==0){char payload[2048];memset(payload,'x',sizeof(payload));for(int i=0;i<4000;i++)write(1,payload,sizeof(payload));return 0;}
 if(argc>1 && strcmp(argv[1],"--sleep")==0){sleep(30);return 0;}
 if(getpid()!=1){fprintf(stderr,"PID_NOT_ONE:%d\n",getpid());return 2;}
 if(access("/etc/passwd",F_OK)==0){fprintf(stderr,"HOST_ETC_VISIBLE\n");return 3;}
 if(access("/proc/self",F_OK)==0){fprintf(stderr,"HOST_PROC_VISIBLE\n");return 4;}
 int fd=open("/workspace/input.txt",O_RDONLY); if(fd<0)return 5;
 char buf[16]={0}; if(read(fd,buf,8)<2)return 6;close(fd);
 if(strcmp(buf,"sentinel")!=0)return 7;
 fd=open("/workspace/pwned.txt",O_WRONLY|O_CREAT,0600);
 if(fd>=0){close(fd);fprintf(stderr,"WORKSPACE_RW\n");return 8;}
 fd=open("/tmp/probe.txt",O_CREAT|O_WRONLY,0600);if(fd<0)return 9;
 if(write(fd,"ok",2)!=2)return 10;close(fd);
 int s=socket(AF_INET,SOCK_STREAM,0);
 if(s>=0){struct sockaddr_in dst={.sin_family=AF_INET,.sin_port=htons(443),.sin_addr.s_addr=htonl(0x01010101)};
  if(connect(s,(struct sockaddr*)&dst,sizeof(dst))==0){fprintf(stderr,"NETWORK_OK\n");return 11;} close(s);}
 puts("NEXUS_ROOTLESS_PROBE_PASS");return 0;
}
