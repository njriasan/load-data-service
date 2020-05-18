# python 3
FROM continuumio/miniconda3:4.6.14

MAINTAINER K. Shankari (shankari@eecs.berkeley.edu)
# set working directory
WORKDIR /usr/src/app

# clone from repo. If you forked the existing repo change this to the repo you are using
RUN git clone https://github.com/njriasan/load-data-service.git .

# setup python environment.
RUN setup/setup.sh

WORKDIR /usr/src/app

# cleanup
RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

#add start script.
# this is a redundant workdir setting, but it doesn't harm anything and might
# be useful if the other one is removed for some reason
WORKDIR /usr/src/app
ADD start_script.sh /usr/src/app/start_script.sh
RUN chmod u+x /usr/src/app/start_script.sh

CMD ["/bin/bash", "/usr/src/app/start_script.sh"]
