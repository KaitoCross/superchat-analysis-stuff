
CREATE DATABASE superchat_data;

CREATE TABLE channel(
    id varchar,
    name varchar,
    tracked bool,
    color char(6),
    PRIMARY KEY(id)
);
CREATE TABLE chan_names(
    id varchar,
    name varchar,
    time_discovered timestamptz,
    time_used timestamptz,
    PRIMARY KEY (id,name),
    CONSTRAINT chan_id FOREIGN KEY (id) REFERENCES channel(id)
);
CREATE TABLE video(
    video_id varchar,
    channel_id varchar,
    title varchar,
    caught_while varchar,
    live varchar,
    old_title varchar,
    membership bool,
    length bigint,
    createdDateTime timestamptz,
    publishDateTime timestamptz,
    startedLogAt timestamptz,
    endedLogAt timestamptz,
    scheduledStartTime timestamptz,
    actualStartTime timestamptz,
    actualEndTime timestamptz,
    retries_of_rerecording integer,
    retries_of_rerecording_had_scs integer,
    PRIMARY KEY (video_id),
    CONSTRAINT chan_id FOREIGN KEY (channel_id) REFERENCES channel(id)
);
CREATE TABLE messages(
    video_id varchar,
    chat_id varchar,
    user_id varchar,
    message_txt varchar,
    time_sent timestamptz,
    currency char(4),
    value numeric(15,6),
    color bigint,
    CONSTRAINT v_id FOREIGN KEY (video_id) REFERENCES video(video_id),
    constraint c_id FOREIGN KEY (user_id) REFERENCES channel(id),
    PRIMARY KEY (video_id,user_id,message_txt,time_sent)
);

CREATE TABLE area(
    areano int,
    area_name varchar,
    PRIMARY KEY (areano)
);

CREATE TABLE currency(
    code varchar,
    area int,
    PRIMARY KEY(code),
    constraint area_id FOREIGN KEY (area) REFERENCES area(areano)
);

CREATE TABLE agency(
    id int,
    name varchar,
    PRIMARY KEY(id)
);

CREATE TABLE unit(
    id int,
    ag_id int,
    name varchar,
    PRIMARY KEY(id),
    constraint ag_id FOREIGN KEY (ag_id) REFERENCES agency(id)
);

CREATE TABLE unit_members(
    unit_id int,
    chan_id varchar,
    constraint u_id FOREIGN KEY (unit_id) REFERENCES unit(id),
    constraint c_id FOREIGN KEY (chan_id) REFERENCES channel(id),
    primary key (unit_id,chan_id)
);

INSERT INTO agency VALUES (1,'Hololive'), (2,'Nijisanji'), (3,'PRISM Project');
INSERT INTO unit VALUES (1,1,'Myth'), (2,1,'Council'), (3,1,'Project: HOPE');
INSERT INTO unit_members VALUES (1,'UCHsx4Hqa-1ORjQTh9TYDhww'),(1,'UCL_qhgtOy0dy1Agp8vkySQg'),(1,'UCoSrY_IQQVpmIRZ9Xf-y93g'),(1,'UCMwGHR0BTZuLsmjY_NT5Pwg'),(1,'UCyl1z3jo3XHR1riLFKG5UAg');
INSERT INTO unit_members VALUES (2,'UCsUj0dszADCGbF3gNrQEuSQ'),(2,'UCgmPnx-EEeOrZSg5Tiw7ZRQ'),(2,'UCmbs8T6MWqUHP1tIQvSgKrg'),(2,'UCO_aKKYxn4tvrqPjcTzZ6EQ'),(2,'UC3n5uGu18FoCy23ggWWp8tA');
INSERT INTO unit_members VALUES (3,'UC8rcEBzJSleTkf_-agPM20g');
INSERT INTO unit VALUES (6,2,'Ethyria'), (8,2,'Noctyx'), (7,2,'Luxiem'), (5,2,'OBSYDIA'), (4,2,'LazuLight');
INSERT INTO unit_members VALUES (4,'UCIeSUTOTkF9Hs7q3SGcO-Ow'),(4,'UCu-J8uIXuLZh16gG-cT1naw'),(4,'UCP4nMSTdwU1KqYWu3UH5DHQ');
INSERT INTO unit_members VALUES (5,'UCV1xUwfM2v2oBtT3JNvic3w'),(5,'UCgA2jKRkqpY_8eysPUs8sjw'),(5,'UC4WvIIAo89_AzGUh1AZ6Dkg');
INSERT INTO unit_members VALUES (6,'UCkieJGn3pgJikVW8gmMXE2w'),(6,'UC47rNmkDcNgbOcM-2BwzJTQ'),(6,'UCBURM8S4LH7cRZ0Clea9RDA'),(6,'UCR6qhsLpn62WVxCBK1dkLow');
INSERT INTO unit_members VALUES (7,'UC7Gb7Uawe20QyFibhLl1lzA'),(7,'UC4yNIKGvy-YUrwYupVdLDXA'),(7,'UCckdfYDGrjojJM28n5SHYrA'),(7,'UCG0rzBZV_QMP4MtWg6IjhEA'),(7,'UCIM92Ok_spNKLVB5TsgwseQ');
INSERT INTO unit_members VALUES (8,'UCuuAb_72QzK0M1USPMEl1yw'),(8,'UCGhqxhovNfaPBpxfCruy9EA'),(8,'UChJ5FTsHOu72_5OVx0rvsvQ'),(8,'UCQ1zGxHrfEmmW4CPpBx9-qw'),(8,'UCSc_KzY_9WYAx9LghggjVRA');
INSERT INTO unit VALUES (9,1,'JP Gen 6');
INSERT INTO unit_members VALUES (9,'UC_vMYWcDjmfdpH6r4TTn1MQ'),(9,'UCIBY1ollUsauvVi4hW4cumw'),(9,'UC6eWCld0KwmyHFbAqK3V-Rw'),(9,'UCs9_O1tRPMQTHQ-N_L6FU2g'),(9,'UCENwRMx5Yh42zWpzURebzTw');
INSERT INTO unit VALUES (10,3,'Gen 1'), (11,3,'Gen 2'), (12,3,'Gen 3'), (13,3,'Gen 4');
INSERT INTO unit_members VALUES (10,'UC2hWFlqMew61Jy6A8zu5HzQ'),(10,'UCRWF6QSuklmwY3UJHyVTQ1w'),(10,'UCZfQRuwSLty74QAj55BaKlA');
INSERT INTO unit_members VALUES (11,'UCnYhIk9aGEx_bIgheVjs53w'),(11,'UCBJFsaCvgBa1a9BnEaxu97Q');
INSERT INTO unit_members VALUES (12,'UCswvd6_YWmd6riRk-8oT-sA'),(12,'UCw1KNjVqfrJSfcFd6zlcSzA'),(12,'UCpeRj9-GaLGNUoKdI5I7vZA'),(12,'UC0ZTVxCHkZanT5dnP2FZD4Q');
INSERT INTO unit_members VALUES (13,'UCgM1sly6rnxqWe8GLbceEag'),(13,'UCkJ64W0J7R0zCSAsZfRIhVQ'),(13,'UCx_A6fns9qKjybu-6k0ur1g'),(13,'UCKRGwowORbvAnoeZ-G06duQ');

INSERT INTO area VALUES
    (1, 'North America'),(2,'South America'),(3,'Europe'),(4,'Africa'),(5,'Asia'),(6,'Oceania');

INSERT INTO currency(area,code) VALUES
(1,'USD'),(1,'CAD'),(1,'MXN'),
(2,'ARS'),(2,'BOB'),(2,'BRL'),(2,'CLP'),(2,'COP'),(2,'CRC'),(2,'DOP'),(2,'GTQ'),(2,'HNL'),(2,'NIO'),(2,'PEN'),(2,'PYG'),(2,'UYU'),
(3,'BAM'),(3,'BGN'),(3,'BYN'),(3,'CHF'),(3,'CZK'),(3,'DKK'),(3,'EUR'),(3,'GBP'),(3,'HRK'),(3,'HUF'),(3,'ILS'),(3,'ISK'),(3,'NOK'),(3,'PLN'),(3,'RON'),(3,'RSD'),(3,'RUB'),(3,'SEK'),(3,'TRY'),
(4,'ZAR'),(4,'EGP'),(4,'NGN'),
(5,'AED'),(5,'HKD'),(5,'INR'),(5,'JOD'),(5,'JPY'),(5,'KRW'),(5,'MYR'),(5,'PHP'),(5,'QAR'),(5,'SAR'),(5,'SGD'),(5,'TWD'),
(6,'AUD'),(6,'NZD');