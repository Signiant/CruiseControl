FROM node:0.10.39

RUN mkdir -p /usr/src/app

WORKDIR /usr/src/app

COPY . /usr/src/app

EXPOSE 8080

CMD [ "npm", "start" ]
