#Copyright (C) 2020  David D. Anastasio

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU Affero General Public License as published
#by the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.

#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
#GNU Affero General Public License for more details.

#You should have received a copy of the GNU Affero General Public License
#along with this program.  If not, see <https://www.gnu.org/licenses/>.

FROM registry.fedoraproject.org/fedora-minimal

RUN microdnf install -y python3 python3-pip
RUN pip install imapclient requests

WORKDIR /app
COPY . /app
RUN mkdir /app/config
VOLUME /app/config
CMD /usr/bin/python3 /app/main.py
