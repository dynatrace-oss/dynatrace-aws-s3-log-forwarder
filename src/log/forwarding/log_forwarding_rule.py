# Copyright 2022 Dynatrace LLC

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#      https://www.apache.org/licenses/LICENSE-2.0

#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.


import re
from dataclasses import dataclass
from typing import Optional
from log.processing.log_processing_rules import AVAILABLE_LOG_SOURCES


@dataclass(frozen=True)
class LogForwardingRule:
    name: str
    s3_prefix_expression: re.Pattern
    source: str
    source_name: Optional[str]
    annotations: Optional[dict]
    sinks: Optional[list]

    def validate(self):
        if self.source not in AVAILABLE_LOG_SOURCES:
            raise ValueError("Invalid log source")

        if not isinstance(self.s3_prefix_expression,re.Pattern):
            raise ValueError("s3_prefix_expression is not a regex pattern.")
        
        if (not isinstance(self.annotations,dict)) and self.annotations is not None:
            print(type(self.annotations))
            raise ValueError("annotations are invalid.")
        
        if (not isinstance(self.sinks, list)) and self.sinks is not None:
            raise ValueError("Invalid sinks configuration")
        
        for i in [self.name, self.source]:
            if not isinstance(i,str):
                raise ValueError(f"{i} is not a str.")
        
        if self.source == "aws" and self.source_name is not None:
            raise ValueError("Source name must be 'None' for aws sources.")
        elif self.source == 'custom' and self.source_name is None:
            raise ValueError("source_name requires a value when source is 'custom'")

    def __post_init__(self):
        if self.sinks is None:
            object.__setattr__(self,"sinks",["1"])
        if self.source == "generic" and self.source_name is None:
            object.__setattr__(self,"source_name","generic")
        self.validate()


    def match(self, key_name):
        '''
        Checks whether the regular expression provided matches the key prefix.
        '''
        return re.match(self.s3_prefix_expression, key_name) is not None


